"""LangGraph investigator over the MCP graph tools (no UI).

The LLM only picks tools and writes explanations; all graph work happens in
the MCP server (the same stdio server external clients use), reached here
through the MCP client. Final answers are grounding-checked in code: every
node_id and quoted name must come from tool results.
"""
import asyncio
import json
import operator
import os
import re
import sys
from datetime import datetime
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langgraph.graph import END, StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.graph.rel_types import SOFT_REL_TYPES
from backend.llm.client import LLMClient

SYSTEM = """You investigate public ICIJ leak data (Offshore Leaks and Panama Papers) held in a graph.
Rules:
- Resolve every person/company name with search_entity first; it returns node_ids. If several candidates match and none matches the user's text exactly, stop and ask the user to pick one — never silently proceed with one of them.
- strongest_connection and shared_neighbors accept ONLY node_ids already returned by search_entity; anything else is rejected.
- Never call a tool with the same node_id on both sides: a record is not a connection to itself and the tools reject it. If one name is the subject on both sides of the question (e.g. the same name on two datasets), call search_entity for it and use the ids it returns.
- Use strongest_connection for the recorded path between two node_ids, shared_neighbors for what two node_ids have in common.
- Restate node ids and names exactly as tool results returned them (spelling, punctuation and case included). Never invent, guess or "correct" a name or id, and never put a question mark or an uncertain guess inside an answer.
- State ONLY facts present in tool results. If there is no path, or the path is hub-blocked, say so plainly and name the excluded hubs.
- If the tool result carries a score_note, the score is not applicable: state it with wording from score_note (e.g. "not applicable: direct link, no intermediate nodes") and never print a numeric score like 0.00.
- When there is no hub-respecting path, use exactly this shape: "no hub-respecting path within N hops" (N = the max_hops used); if the reference found a longer unfiltered route, add "an unfiltered reference path exists at K hops through <named hub>". Never call the longer route "the strongest connection". Count path length in hops, never nodes. A reference_path under "excluded" is not an informative connection and never counts toward the ranked paths.
- strongest_connection also lists up to 8 ranked paths, best first. In the answer, state how many recorded paths were found, mark the first as the strongest, and note that the Paths panel shows 4 at a time with the rest on the next page when there are more than 4.
- Neutral language: say "connection relevance" and "possible match", never "suspicious" or "criminal". Appearing in the data implies no wrongdoing.
- If a tool result has includes_possible_match=true, call those links "possible match" edges (soft, similar/same_as/underlying); they are not confirmed identities.
- Keep the final answer short: the finding, the path in one line, the score.""
"""

LIMITATIONS = ("Connection relevance only: appearing in this public ICIJ leak data "
               "implies no wrongdoing. Scores rank how informative a recorded connection is. "
               "Soft-edge links are possible matches, never confirmed identities.")

SERVER_CMD = [sys.executable, "backend/mcp_server/server.py"]


def _norm(s):
    return " ".join((s or "").casefold().split())


def _bare(s):
    return re.sub(r"[^\w\s]", "", _norm(s))


# Spot table for country claims: correct code per country name. Only used to
# flag pairings like "VGB is Bermuda" that contradict the tool evidence.
CC_NAME_TO_CODE = {
    "bermuda": "BMU", "british virgin islands": "VGB", "virgin islands": "VGB",
    "cyprus": "CYP", "hong kong": "HKG", "singapore": "SGP", "taiwan": "TWN",
    "venezuela": "VEN", "samoa": "WSM", "panama": "PAN", "malta": "MLT",
    "seychelles": "SYC", "belize": "BLZ", "nevis": "KNA", "cook islands": "COK",
    "marshall islands": "MHL", "bahamas": "BHS", "barbados": "BRB", "aruba": "ABW",
}

# Identity wording that may only stand on a hard (core) link. When every
# recorded link between the records is soft, these spans are deterministically
# downgraded to possible-match wording and reported in the grounding flags.
# The first pattern must run before the verb one so "are the same company"
# becomes one clean replacement, not "are a possible match ... company".
_IDENTITY_PATTERNS = (
    re.compile(r"\bthe same (?:company|person|entity|firm|record|individual)\b", re.I),
    re.compile(r"\b(are|is|were|was) the same\b", re.I),
    re.compile(r"\bidentical\b", re.I),
    re.compile(r"\bstrong\b"),  # bare "strong"; "strongest" has no word boundary after "strong"
)
_POSSIBLE_MATCH = "a possible match (not a confirmed identity)"


def _summarize(tool, payload):
    if payload.get("error"):
        return {"error": str(payload["error"])[:120]}
    if tool == "strongest_connection_tool":
        p = payload.get("path") or {}
        return {"path_length": p.get("length"), "score": payload.get("score"),
                "n_paths": len(payload.get("paths") or []),
                "paths_truncated": bool(payload.get("paths_truncated")),
                "reference_path_length": (payload.get("reference_path") or {}).get("length"),
                "hubs": len(payload.get("excluded_hubs", []))}
    if tool == "search_entity_tool":
        s = {"n_results": len(payload.get("results", []))}
        if payload.get("auto_pair"):
            s["auto_pair"] = [payload["auto_pair"]["id_a"], payload["auto_pair"]["id_b"]]
        return s
    if tool == "shared_neighbors_tool":
        return {"n_neighbors": len(payload.get("neighbors", [])),
                "hubs": len(payload.get("excluded_hubs", []))}
    return {"keys": sorted(payload.keys())}


def _auto_pair(name, payload, question):
    """A name with exactly two exact hits from different sourceIDs is the two
    sides of a same-name question (PEARL OCEAN pattern: the same name on two
    datasets). Resolving BOTH ids here keeps one candidate pick from pinning
    both sides to one record; the caller adds the returned note to the tool
    message and the trace, so the model compares the two records instead.
    """
    if not name or _bare(name) not in _bare(question or ""):
        return None
    exact = [r for r in payload.get("results", []) if _norm(r.get("name")) == _norm(name)]
    if len(exact) != 2:
        return None
    if len({str(r.get("sourceID")) for r in exact}) != 2:
        return None
    exact.sort(key=lambda r: str(r.get("node_id")))  # deterministic id_a/id_b order
    a, b = exact
    note = (f"AUTO-PAIR: '{name}' has exactly two exact records from different sourceIDs — "
            f"id_a {a['node_id']} ({a.get('sourceID')}) and id_b {b['node_id']} ({b.get('sourceID')}). "
            "They are the two endpoints of this question. Call "
            f"strongest_connection(source_id={a['node_id']}, target_id={b['node_id']}). "
            "Never call shared_neighbors or get_neighbors with the same id on both sides.")
    payload["auto_pair"] = {"id_a": str(a["node_id"]), "id_b": str(b["node_id"]), "note": note}
    return payload["auto_pair"]


def _for_llm(payload):
    # The full candidate rows are only for the UI; shrink the ranked paths so a
    # broad multi-path result still fits the tool-message budget (4000 chars).
    if "reference_length" not in payload:
        return payload
    slim = dict(payload)
    slim["paths"] = [{"length": p.get("length"), "score": p.get("score"),
                      "score_note": p.get("score_note"),
                      "includes_possible_match": p.get("includes_possible_match"),
                      "nodes": [n.get("name") or n.get("node_id") for n in p.get("nodes") or []]}
                     for p in payload.get("paths") or []]
    rp = payload.get("reference_path")
    if rp:
        slim["reference_path"] = {"length": rp.get("length"), "excluded": True,
                                  "nodes": [{"node_id": n.get("node_id"), "name": n.get("name"),
                                             "is_hub": n.get("is_hub")} for n in rp.get("nodes") or []]}
    return slim


_STAR_KEYS = ("node_id", "name", "display_name", "labels", "degree_core", "country_codes", "sourceID",
              "hub_threshold", "allow_hub", "is_hub", "note", "total_neighbors", "shown",
              "neighbors", "excluded_hubs", "includes_possible_match", "possible_match_edges")


def _star_payload(p):
    """The get_neighbors result, trimmed for the UI's neighbour star graph."""
    return {k: p.get(k) for k in _STAR_KEYS}


def _ground(answer, evidence, question="", pins=()):
    ids, names, degrees, terms = set(), [], set(), []
    # An id the user typed in the question or pinned from a candidate list is
    # grounded by definition — the user supplied it, the model is echoing it.
    ids.update(re.findall(r"\b\d{5,}\b", question or ""))
    ids.update(str(v) for v in pins or ())
    for payload in evidence:
        for key in ("path", "neighbors", "results", "excluded_hubs", "breakdown"):
            items = payload.get(key)
            if isinstance(items, dict):
                items = [items]
            for it in (items or []):
                if isinstance(it, dict):
                    if it.get("node_id"):
                        ids.add(str(it["node_id"]))
                    if it.get("name"):
                        names.append(str(it["name"]))
                    if it.get("degree_core") is not None:
                        degrees.add(str(it["degree_core"]))
        # Names/ids/terms from every ranked path and the reference count as
        # grounded evidence, so the model may quote them without flags.
        variants = [payload.get("path") or {}] + list(payload.get("paths") or [])
        if payload.get("reference_path"):
            variants.append(payload["reference_path"])
        for p in variants:
            for n in p.get("nodes", []):
                if n.get("node_id"):
                    ids.add(str(n["node_id"]))
                if n.get("name"):
                    names.append(str(n["name"]))
                if n.get("degree_core") is not None:
                    degrees.add(str(n["degree_core"]))
            for edge in p.get("edges", []):
                for k in ("link", "role_category", "rel_type"):
                    if edge.get(k):
                        terms.append(str(edge[k]))
        for n in payload.get("neighbors", []):
            for v in n.get("via", []):
                for k in ("link", "role_category", "rel_type"):
                    if v.get(k):
                        terms.append(str(v[k]))
    flags, stripped = [], False
    for tok in set(re.findall(r"\b\d{5,}\b", answer)):
        if tok not in ids and tok not in degrees:
            flags.append(f"unknown node_id {tok}")
            answer = answer.replace(tok, "[unverified id removed]")
            stripped = True
    codes = set()
    for payload in evidence:
        for key in ("path", "neighbors", "results", "excluded_hubs"):
            items = payload.get(key)
            if isinstance(items, dict):
                items = [items]
            for it in (items or []):
                if isinstance(it, dict) and it.get("country_codes"):
                    codes.update(re.findall(r"[A-Za-z]{3}", str(it["country_codes"])))
    codes = {c.upper() for c in codes}
    nametoks = set()
    for n in names:
        nametoks.update(_bare(n).split())
    # Lookarounds, not \b: the last 3 letters of a longer uppercase word (the
    # "TED" in "LIMITED") must never read as a country code.
    for tok in set(re.findall(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])", answer)):
        if tok not in codes and tok.casefold() not in nametoks:
            flags.append(f"country code {tok} not in tool results")
    low = answer.casefold()
    for name, code in CC_NAME_TO_CODE.items():
        i = low.find(name)
        if i < 0:
            continue
        # Match on the FULL answer (so lookarounds keep their context) and keep
        # the hits whose span falls inside the window around the country name.
        lo, hi = max(0, i - 60), min(len(answer), i + len(name) + 60)
        others = {m.group(0) for m in re.finditer(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])", answer)
                  if lo <= m.start() and m.end() <= hi} - {code}
        if others:
            flags.append(f"country mismatch: {name!r} shown with {sorted(others)}, expected {code}")
    lowered = [_bare(n) for n in names] + [_bare(t) for t in terms]
    ql = _bare(question)
    for span in set(re.findall(r'"([^"]+)"', answer)):
        if _bare(span) in ql:
            continue  # echoing the user's own wording needs no verification
        if not any(_bare(span) in n for n in lowered):
            flags.append(f"unverified quoted name {span!r}")
    # A claim about shared neighbours needs a shared_neighbors result; without
    # one the sentence is ungrounded and removed (the model may otherwise
    # derive "shared" from a plain neighbour list).
    shared_removed = 0
    if re.search(r"shared (?:neighbor|neighbour)", answer, re.I) \
            and not any("grouped_by_edge_type" in p for p in evidence):
        sentences = re.split(r"(?<=[.!?])\s+", answer)
        kept = [s for s in sentences if not re.search(r"shared (?:neighbor|neighbour)", s, re.I)]
        shared_removed = len(sentences) - len(kept)
        answer = " ".join(kept).strip()
    # Whitelist "strongest" via the boundary above: only a bare "strong" claim
    # is a score-ish claim, and only downgraded when nothing but soft edges
    # link the records.
    soft_edge = core_edge = False
    for payload in evidence:
        variants = [payload.get("path") or {}] + list(payload.get("paths") or [])
        if payload.get("reference_path"):
            variants.append(payload["reference_path"])
        for p in variants:
            for e in p.get("edges") or []:
                if e.get("rel_type") in SOFT_REL_TYPES:
                    soft_edge = True
                else:
                    core_edge = True
    soft_only = (soft_edge and not core_edge) or (
        not soft_edge and not core_edge
        and any(p.get("includes_possible_match") and p.get("possible_match_edges")
                for p in evidence))
    identity_replaced = []

    def _downgrade(m):
        verb = m.group(1) if m.lastindex else None
        identity_replaced.append(m.group(0))
        return f"{verb} {_POSSIBLE_MATCH}" if verb else _POSSIBLE_MATCH

    if soft_only:
        for pat in _IDENTITY_PATTERNS:
            answer = pat.sub(_downgrade, answer)
    return answer, {"unknown_ids": [f for f in flags if f.startswith("unknown node_id")],
                    "unknown_names": [f for f in flags if f.startswith("unverified quoted")],
                    "country_flags": [f for f in flags if f.startswith("country")],
                    "identity_claims_replaced": identity_replaced,
                    "shared_claims_removed": shared_removed,
                    "stripped": stripped}


class S(TypedDict):
    messages: Annotated[list, operator.add]
    trace: Annotated[list, operator.add]
    evidence: Annotated[list, operator.add]
    answer: str
    output: dict


def build_graph(session, schemas, llm, hook=None, pins=None):
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                               "parameters": t.input_schema}} for t in schemas]
    # Pins come from the UI click on an ambiguity candidate: the user has
    # already chosen the record, so the LLM must reuse that node_id and never
    # re-search the name (D13). Keyed by normalized name.
    pins = {_norm(k): (k, str(v)) for k, v in (pins or {}).items() if k and v}
    pin_lines = "\n".join(f'- "{orig}" -> node_id {vid}' for orig, vid in pins.values())
    pin_system = ("The user has already picked specific records (pinned). For each name below use "
                  "exactly the given node_id and do NOT call search_entity for that name:\n" + pin_lines
                  + "\nIf one of those names is the subject on BOTH sides of the question (e.g. the "
                    "same name on two datasets), call search_entity_tool for that name once: when "
                    "exactly two exact records from different sourceIDs exist, the tool auto-pairs "
                    "them and tells you the two ids to compare."
                  ) if pin_lines else ""

    async def decide(state):
        if llm.calls >= llm.max_calls:
            msg = await asyncio.to_thread(llm.chat, state["messages"] + [
                {"role": "user", "content": "Budget spent. Write the final answer from tool results only."}])
            return {"messages": [msg], "answer": msg.content or ""}
        system = [{"role": "system", "content": SYSTEM}]
        if pin_system:
            system.append({"role": "system", "content": pin_system})
        # The LLM call is blocking (sync HTTP); run it off the event loop so
        # streaming stays responsive and the request timeout can cancel runs.
        msg = await asyncio.to_thread(llm.chat, system + state["messages"], tools=tools)
        out = {"messages": [msg]}
        if not getattr(msg, "tool_calls", None):
            out["answer"] = msg.content or ""
        return out

    async def act(state):
        calls = state["messages"][-1].tool_calls or []
        question = state["messages"][0]["content"] if state["messages"] else ""
        # id -> (queried name, matched name, candidate count) from searches so far
        known = {}
        for p in state["evidence"]:
            if "results" in p and "query" in p:
                for r in p["results"]:
                    known.setdefault(str(r["node_id"]),
                                     (p["query"], r.get("name", ""), len(p["results"])))
        for orig, vid in pins.values():
            known[vid] = (orig, orig, 1)  # pinned: a single, exact resolution
        messages, trace, evidence = [], [], []
        for tc in calls:
            args = json.loads(tc.function.arguments or "{}")
            # A pinned name is never re-searched by the model, but the run
            # re-checks the name once: a pick pins ONE side of a same-name
            # question, and the other record must stay reachable (auto-pair).
            if tc.function.name == "search_entity_tool" and _norm(args.get("name", "")) in pins:
                orig, vid = pins[_norm(args["name"])]
                real = {"query": args.get("name"), "results": []}
                try:
                    res2 = await session.call_tool("search_entity_tool", {"name": args.get("name")})
                    real = json.loads(res2.content[0].text)
                except Exception:
                    pass
                ap = _auto_pair(args.get("name"), real, question)
                text = ""
                if ap:
                    payload, text = real, ap["note"] + "\n"
                    payload["query"] = args.get("name")
                    payload["note"] = ap["note"]
                    summary = {"auto_pair": [ap["id_a"], ap["id_b"]]}
                else:
                    row = next((r for r in real.get("results", [])
                                if str(r.get("node_id")) == str(vid)), None)
                    payload = {"query": args.get("name"), "pinned": True,
                               "results": [row or {"node_id": vid, "name": orig, "labels": [],
                                                   "country_codes": None, "degree_core": None,
                                                   "sourceID": None}],
                               "note": f"'{orig}' is pinned to node_id {vid}; use it directly."}
                    summary = {"pinned": vid}
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": text + json.dumps(payload)[:4000]})
                trace.append({"step": len(state["trace"]) + len(trace) + 1, "tool": tc.function.name,
                              "args": args, "cypher": real.get("cypher"), "result_summary": summary})
                evidence.append(payload)
                if hook is not None:
                    hook(trace[-1])
                continue
            if tc.function.name in ("strongest_connection_tool", "shared_neighbors_tool"):
                ids = [str(args.get(k, "")) for k in ("source_id", "target_id", "id_a", "id_b")
                       if args.get(k)]
                unknown = [i for i in ids if i not in known]
                if unknown:
                    err = {"error": f"node_id(s) {unknown} never appeared in search results; "
                                    "resolve names with search_entity first"}
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(err)})
                    trace.append({"step": len(state["trace"]) + len(trace) + 1, "tool": tc.function.name,
                                  "args": args, "cypher": None, "result_summary": {"blocked": err["error"][:80]}})
                    continue
            res = await session.call_tool(tc.function.name, args)
            payload = json.loads(res.content[0].text)
            auto_note = ""
            if tc.function.name == "search_entity_tool":
                ap = _auto_pair(args.get("name", ""), payload, question)
                if ap:
                    auto_note = ap["note"]
            notice = ""
            if tc.function.name in ("strongest_connection_tool", "shared_neighbors_tool"):
                for k in ("source_id", "target_id", "id_a", "id_b"):
                    if args.get(k) and str(args[k]) in known:
                        qn, rn, n = known[str(args[k])]
                        if n > 1 and _norm(rn) != _norm(qn):
                            notice = (f"AMBIGUITY NOTICE: '{qn}' matched {n} candidates and "
                                      f"'{rn}' is not an exact match. List the candidates and "
                                      "ask the user to pick before concluding.")
                            break
                if notice:
                    payload["_notice"] = notice
            text = (("NOTICE: " + notice + "\n") if notice else "") + \
                   ((auto_note + "\n") if auto_note else "") + json.dumps(_for_llm(payload))[:4000]
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
            entry = {"step": len(state["trace"]) + len(trace) + 1, "tool": tc.function.name,
                     "args": json.loads(tc.function.arguments or "{}"),
                     "cypher": payload.get("cypher"),
                     "result_summary": _summarize(tc.function.name, payload)}
            trace.append(entry)
            evidence.append(payload)
            if hook is not None:
                hook(entry)
        return {"messages": messages, "trace": trace, "evidence": evidence}

    def route(state):
        last = state["messages"][-1]
        return "act" if getattr(last, "tool_calls", None) else "compose"

    def compose(state):
        answer, grounding = _ground(state.get("answer", ""), state["evidence"],
                                    state["messages"][0]["content"] if state["messages"] else "",
                                    pins=[vid for _o, vid in pins.values()])
        if not answer.strip():
            # The model sometimes ends the loop with an empty message; never
            # return silence — synthesize from tool evidence instead.
            found = [p for p in state["evidence"] if p.get("results")]
            if found:
                lines = [f"{r['name']} (node_id {r['node_id']}, {','.join(r['labels'])}, "
                         f"{r['country_codes']}, degree {r['degree_core']})"
                         for r in found[-1]["results"][:10]]
                answer = "Candidates found:\n" + "\n".join(f"- {l}" for l in lines)
                grounding["stripped"] = "empty-model-answer-replaced"
            else:
                answer = ("No answer was produced and no tool evidence exists. "
                          "Please rephrase the question with exact names.")
                grounding["stripped"] = "empty-model-answer-no-evidence"
        strongest = [p for p in state["evidence"] if "reference_length" in p]
        shared = [p for p in state["evidence"] if "grouped_by_edge_type" in p]
        # Only a get_neighbors payload may drive the star: shared_neighbors also
        # carries hub_threshold + neighbors but has no centre node (id_a/id_b),
        # so it would render as a centre-less "unknown label" star (the PEARL
        # bug). The star is the ONE payload with a real node_id centre.
        nbr = [p for p in state["evidence"] if "neighbors" in p and "hub_threshold" in p
               and p.get("node_id") is not None and "id_a" not in p]
        s = strongest[-1] if strongest else {}
        path = (s.get("path") or {})
        hubs, seen_hubs = [], set()
        for h in s.get("excluded_hubs", []) + [h for p in shared for h in p.get("excluded_hubs", [])]:
            if h.get("node_id") not in seen_hubs:
                seen_hubs.add(h.get("node_id"))
                hubs.append(h)
        # Ambiguity = a name that had several exact matches and is not pinned.
        # Hand the UI structured rows so it can offer click-to-pin buttons.
        candidates, seen_c = [], set()
        for p in state["evidence"]:
            if p.get("pinned") or "results" not in p or "query" not in p:
                continue
            if p.get("auto_pair"):
                # Both records are already the two endpoints (auto-paired): a
                # click-to-pin list would be a step backwards.
                continue
            q = p["query"]
            if _norm(q) in pins:
                continue
            exact = [r for r in p["results"] if _norm(r.get("name")) == _norm(q)]
            if len(exact) > 1:
                for r in exact:
                    ck = (q, str(r.get("node_id")))
                    if ck in seen_c:
                        continue
                    seen_c.add(ck)
                    candidates.append({"for_name": q, "node_id": r.get("node_id"), "name": r.get("name"),
                                       "labels": r.get("labels", []), "country_codes": r.get("country_codes"),
                                       "degree_core": r.get("degree_core"), "sourceID": r.get("sourceID")})
        return {"output": {
            "answer": answer,
            "candidates": candidates,
            "pinned": [{"for_name": orig, "node_id": vid} for orig, vid in pins.values()],
            "evidence_path": {"nodes": path.get("nodes", []), "edges": path.get("edges", [])} if path else {},
            "star": _star_payload(nbr[-1]) if nbr else None,
            # Total = mean D3 rarity over the intermediate nodes only (endpoints
            # are fixed by the question, so they contribute nothing). None when
            # there is no path, and also for a direct link (no intermediates) —
            # in that case score_note explains why the score does not apply.
            "score": s.get("score"),
            "score_note": s.get("score_note"),
            "score_breakdown": s.get("breakdown", []),
            "paths": s.get("paths") or [],
            "paths_truncated": bool(s.get("paths_truncated")),
            "reference_path": s.get("reference_path"),
            "excluded_hubs": hubs,
            "trace": state["trace"],
            "grounding": grounding,
            "llm_calls": llm.calls,
            "limitations": LIMITATIONS}}

    g = StateGraph(S)
    g.add_node("decide", decide)
    g.add_node("act", act)
    g.add_node("compose", compose)
    g.set_entry_point("decide")
    g.add_conditional_edges("decide", route, {"act": "act", "compose": "compose"})
    g.add_edge("act", "decide")
    g.add_edge("compose", END)
    return g.compile()


def _first_error(ex):
    """Unwrap the MCP stdio closure's ExceptionGroup down to the real error.

    Exiting stdio_client/ClientSession wraps whatever the body raised in an
    ExceptionGroup ("unhandled errors in a TaskGroup"), which would hide clear
    LLM errors (LLMRateLimitedError etc.) behind a generic 502. Cancellation is
    never unwrapped, so request timeouts still surface as cancellations.
    """
    while isinstance(ex, BaseExceptionGroup):
        flat = [e for e in ex.exceptions if not isinstance(e, asyncio.CancelledError)]
        if len(flat) != 1:
            break
        ex = flat[0]
    return ex


def _mcp_params():
    """GRAPH_NAME must be forwarded to the MCP subprocess explicitly: the MCP
    SDK only inherits a safe allowlist of env vars (get_default_environment),
    so without this the subprocess silently falls back to the default graph."""
    return StdioServerParameters(command=SERVER_CMD[0], args=SERVER_CMD[1:], cwd=".",
                                 env={"GRAPH_NAME": os.getenv("GRAPH_NAME", "offshore")})


async def arun(question, on_step=None, pins=None):
    params = _mcp_params()
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                schemas = (await session.list_tools()).tools
                llm = LLMClient()
                app = build_graph(session, schemas, llm, hook=on_step, pins=pins)
                state = {"messages": [{"role": "user", "content": question}],
                         "trace": [], "evidence": [], "answer": "", "output": {}}
                out = await app.ainvoke(state)
                result = out["output"]
                result["provider"] = llm.provider
                os.makedirs("runs", exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                with open(f"runs/run-{ts}.json", "w", encoding="utf-8") as f:
                    json.dump({"question": question, "result": result}, f, ensure_ascii=False)
                return result
    except BaseException as ex:
        inner = _first_error(ex)
        if inner is not ex:
            raise inner from None
        raise


def run(question, on_step=None, pins=None):
    return asyncio.run(arun(question, on_step=on_step, pins=pins))
