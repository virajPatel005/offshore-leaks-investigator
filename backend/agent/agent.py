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

from backend.llm.client import LLMClient

SYSTEM = """You investigate the public ICIJ Offshore Leaks graph.
Rules:
- Resolve every person/company name with search_entity first; it returns node_ids. If several candidates match and none matches the user's text exactly, stop and ask the user to pick one — never silently proceed with one of them.
- strongest_connection and shared_neighbors accept ONLY node_ids already returned by search_entity; anything else is rejected.
- Use strongest_connection for the recorded path between two node_ids, shared_neighbors for what two node_ids have in common.
- State ONLY facts present in tool results. If there is no path, or the path is hub-blocked, say so plainly and name the excluded hubs.
- When there is no hub-respecting path, use exactly this shape: "no hub-respecting path within N hops" (N = the max_hops used); if the reference found a longer unfiltered route, add "an unfiltered reference path exists at K hops through <named hub>". Never call the longer route "the strongest connection". Count path length in hops, never nodes.
- Neutral language: say "connection relevance" and "possible match", never "suspicious" or "criminal". Appearing in the data implies no wrongdoing.
- Keep the final answer short: the finding, the path in one line, the score.""
"""

LIMITATIONS = ("Connection relevance only: appearing in this public ICIJ Offshore Leaks data "
               "implies no wrongdoing. Scores rank how informative a recorded connection is.")

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


def _summarize(tool, payload):
    if tool == "strongest_connection_tool":
        p = payload.get("path") or {}
        return {"path_length": p.get("length"), "score": payload.get("score"),
                "hubs": len(payload.get("excluded_hubs", []))}
    if tool == "search_entity_tool":
        return {"n_results": len(payload.get("results", []))}
    if tool == "shared_neighbors_tool":
        return {"n_neighbors": len(payload.get("neighbors", [])),
                "hubs": len(payload.get("excluded_hubs", []))}
    return {"keys": sorted(payload.keys())}


def _ground(answer, evidence, question=""):
    ids, names, degrees, terms = set(), [], set(), []
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
        for edge in (payload.get("path") or {}).get("edges", []):
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
    for tok in set(re.findall(r"\b[A-Z]{3}\b", answer)):
        if tok not in codes and tok.casefold() not in nametoks:
            flags.append(f"country code {tok} not in tool results")
    low = answer.casefold()
    for name, code in CC_NAME_TO_CODE.items():
        i = low.find(name)
        if i >= 0:
            window = answer[max(0, i - 60):i + len(name) + 60]
            others = set(re.findall(r"\b[A-Z]{3}\b", window)) - {code}
            if others:
                flags.append(f"country mismatch: {name!r} shown with {sorted(others)}, expected {code}")
    lowered = [_bare(n) for n in names] + [_bare(t) for t in terms]
    ql = _bare(question)
    for span in set(re.findall(r'"([^"]+)"', answer)):
        if _bare(span) in ql:
            continue  # echoing the user's own wording needs no verification
        if not any(_bare(span) in n for n in lowered):
            flags.append(f"unverified quoted name {span!r}")
    return answer, {"unknown_ids": [f for f in flags if f.startswith("unknown node_id")],
                    "unknown_names": [f for f in flags if f.startswith("unverified quoted")],
                    "country_flags": [f for f in flags if f.startswith("country")],
                    "stripped": stripped}


class S(TypedDict):
    messages: Annotated[list, operator.add]
    trace: Annotated[list, operator.add]
    evidence: Annotated[list, operator.add]
    answer: str
    output: dict


def build_graph(session, schemas, llm, hook=None):
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                               "parameters": t.input_schema}} for t in schemas]

    async def decide(state):
        if llm.calls >= llm.max_calls:
            msg = llm.chat(state["messages"] + [
                {"role": "user", "content": "Budget spent. Write the final answer from tool results only."}])
            return {"messages": [msg], "answer": msg.content or ""}
        msg = llm.chat([{"role": "system", "content": SYSTEM}] + state["messages"], tools=tools)
        out = {"messages": [msg]}
        if not getattr(msg, "tool_calls", None):
            out["answer"] = msg.content or ""
        return out

    async def act(state):
        calls = state["messages"][-1].tool_calls or []
        # id -> (queried name, matched name, candidate count) from searches so far
        known = {}
        for p in state["evidence"]:
            if "results" in p and "query" in p:
                for r in p["results"]:
                    known.setdefault(str(r["node_id"]),
                                     (p["query"], r.get("name", ""), len(p["results"])))
        messages, trace, evidence = [], [], []
        for tc in calls:
            args = json.loads(tc.function.arguments or "{}")
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
            text = ("NOTICE: " + notice + "\n" if notice else "") + json.dumps(payload)[:4000]
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
                                    state["messages"][0]["content"] if state["messages"] else "")
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
        s = strongest[-1] if strongest else {}
        path = (s.get("path") or {})
        hubs, seen_hubs = [], set()
        for h in s.get("excluded_hubs", []) + [h for p in shared for h in p.get("excluded_hubs", [])]:
            if h.get("node_id") not in seen_hubs:
                seen_hubs.add(h.get("node_id"))
                hubs.append(h)
        return {"output": {
            "answer": answer,
            "evidence_path": {"nodes": path.get("nodes", []), "edges": path.get("edges", [])} if path else {},
            # Total = mean D3 rarity over the intermediate nodes only (endpoints
            # are fixed by the question, so they contribute nothing). None when
            # there is no path; 0.0 for a direct link with no intermediates.
            "score": s.get("score"),
            "score_breakdown": s.get("breakdown", []),
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


async def arun(question, on_step=None):
    params = StdioServerParameters(command=SERVER_CMD[0], args=SERVER_CMD[1:], cwd=".")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            schemas = (await session.list_tools()).tools
            llm = LLMClient()
            app = build_graph(session, schemas, llm, hook=on_step)
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


def run(question, on_step=None):
    return asyncio.run(arun(question, on_step=on_step))
