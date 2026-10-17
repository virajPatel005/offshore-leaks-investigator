"""Build web/questions.json from the two hand-maintained question docs.

Sources (single source of truth; this script never invents questions):
  docs/COMPLEX_QUESTIONS.md — sections 1 deep path, 3 hub, 5 multi-step,
    6 ambiguity, 7 possible match, 8 Panama/cross-dataset; other sections
    stay out of the curated sets.
  docs/TEST_QUESTIONS.md — Tiers 2 (multi-step), 3 (hub), 4 (ambiguity) and
    the "Panama / union" tier; Tier 1 / Tier 5 lookups and safety items stay
    out; per-item overrides below move or drop the few misfits.

Rules:
  - Fail loudly if an INCLUDED question has no graph label (offshore|icij);
    the page and the docs can then never drift about which server a
    question needs.
  - status: agent-verified when the heading carries a video-pick star (those
    were run and browser-checked for the demo), when the item body mentions a
    cached answer or a verified agent run, else tool-verified only.
  - video_pick: heading star, or listed in the COMPLEX "Video picks" section.
Run: python3 scripts/build_questions.py  (prints counts + dropped entries)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPLEX = ROOT / "docs" / "COMPLEX_QUESTIONS.md"
TEST = ROOT / "docs" / "TEST_QUESTIONS.md"
OUT = ROOT / "web" / "questions.json"

CATEGORIES = ["Deep path", "Hub changes the answer", "Multi-step",
              "Ambiguity", "Possible match", "Panama and cross-dataset"]
COMPLEX_SECTIONS = {"1": "Deep path", "3": "Hub changes the answer",
                    "5": "Multi-step", "6": "Ambiguity", "7": "Possible match",
                    "8": "Panama and cross-dataset"}
TEST_TIERS = {"Tier 2": "Multi-step", "Tier 3": "Hub changes the answer",
              "Tier 4": "Ambiguity", "Panama / union": "Panama and cross-dataset"}
ITEM_OVERRIDES = {"T4Q4": "Possible match", "T3Q4": "Multi-step"}
ITEM_DROPS = {"T3Q3": "single address lookup, not in the curated categories"}

FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*?):\s*(.*)$")


def read_fields(lines, start):
    """Collect '- Field: value' plus wrapped continuation lines."""
    fields, i = {}, start
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            break
        m = FIELD_RE.match(line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            j = i + 1
            while j < len(lines) and lines[j] and not lines[j].startswith("- ") \
                    and not lines[j].startswith("#"):
                val += " " + lines[j].strip()
                j += 1
            fields[key] = re.sub(r"\s+", " ", val).strip()
            i = j
        else:
            i += 1
    return fields


def split_entries(lines):
    """[(heading, body_lines)] for every '### ...' heading."""
    entries, head, body = [], None, []
    for line in lines:
        if line.startswith("### "):
            if head is not None:
                entries.append((head, body))
            head, body = line[4:].strip(), []
        elif line.startswith("## ") and head is not None:
            entries.append((head, body))
            head, body = None, []
        elif head is not None:
            body.append(line)
    if head is not None:
        entries.append((head, body))
    return entries


def graph_of(fields):
    g = (fields.get("Graph") or "").strip().lower()
    word = re.split(r"[ .(]", g)[0] if g else ""
    return word if word in ("offshore", "icij") else ""


def video_picks(lines):
    ids, inside = set(), False
    for line in lines:
        if line.startswith("## "):
            inside = line.lower().startswith("## video picks")
            continue
        if inside:
            m = re.match(r"^\d+\.\s+(\S+)", line)
            if m:
                ids.add(m.group(1))
    return ids


def parse_complex():
    lines = COMPLEX.read_text(encoding="utf-8").splitlines()
    picks = video_picks(lines)
    out, skipped = [], []
    for head, body in split_entries(lines):
        # find the section this heading belongs to
        start = lines.index("### " + head)
        sec = ""
        for k in range(start, -1, -1):
            m = re.match(r"## (\d+)\.", lines[k])
            if m:
                sec = m.group(1)
                break
        category = COMPLEX_SECTIONS.get(sec)
        eid = head.split()[0]
        if category is None:
            if "- Q:" in "\n".join(body):
                skipped.append((eid, f"section {sec or '?'} not in the curated sets"))
            continue
        fields = read_fields(body, 0)
        q = fields.get("Q", "")
        if not q:
            skipped.append((eid, "no question (not found / note entry)"))
            continue
        g = graph_of(fields)
        star = "★" in head
        out.append({"id": eid, "text": q, "graph": g, "category": category,
                    "why": fields.get("Why", ""), "tools": tools_of(fields.get("Graph", "")),
                    "status": "agent-verified" if (star or eid in picks or "cach" in (fields.get("Expected", "") + fields.get("Why", "")).lower()) else "tool-verified only",
                    "video_pick": bool(star or eid in picks),
                    "source": "COMPLEX_QUESTIONS.md"})
    return out, skipped


def tools_of(graph_line):
    m = re.search(r"Tools[^:]*:\s*(.*)$", graph_line)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def parse_test():
    lines = TEST.read_text(encoding="utf-8").splitlines()
    out, skipped = [], []
    tier = ""
    for head, body in split_entries(lines):
        start = lines.index("### " + head)
        for k in range(start, -1, -1):
            if lines[k].startswith("## "):
                tier = lines[k][3:]
                break
        if "Panama" in tier:
            category, graph = "Panama and cross-dataset", "icij"
        else:
            category = TEST_TIERS.get(tier.split(" \u2014")[0].strip())
            graph = "offshore"
        eid = head.split()[0]
        fields = read_fields(body, 0)
        q = fields.get("Q", "")
        if not q:
            continue  # Mining note and friends have no question
        if category is None:
            skipped.append((eid, f"tier '{tier}' not in the curated sets"))
            continue
        if eid in ITEM_DROPS:
            skipped.append((eid, ITEM_DROPS[eid]))
            continue
        category = ITEM_OVERRIDES.get(eid, category)
        star = "★" in head
        body_text = (fields.get("Expected", "") + fields.get("Why", "")).lower()
        out.append({"id": eid, "text": q, "graph": graph,
                    "category": category, "why": fields.get("Why", ""),
                    "tools": fields.get("Tools", ""),
                    "status": "agent-verified" if (star or "cach" in body_text) else "tool-verified only",
                    "video_pick": star, "source": "TEST_QUESTIONS.md"})
    return out, skipped


def main():
    entries, skipped = parse_complex()
    t_entries, t_skipped = parse_test()
    entries += t_entries
    skipped += t_skipped
    bad = [e for e in entries if not e["graph"]]
    if bad:
        for e in bad:
            print(f"FAIL: {e['id']} ({e['source']}) has no usable Graph label")
        sys.exit(1)
    order = {c: i for i, c in enumerate(CATEGORIES)}
    entries.sort(key=lambda e: (order[e["category"]], e["id"]))
    OUT.write_text(json.dumps({
        "generated_by": "scripts/build_questions.py",
        "generated_from": ["docs/COMPLEX_QUESTIONS.md", "docs/TEST_QUESTIONS.md"],
        "categories": CATEGORIES, "entries": entries}, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(entries)} entries")
    for c in CATEGORIES:
        got = [e for e in entries if e["category"] == c]
        gs = ",".join(sorted({e["graph"] for e in got}))
        picks = ",".join(e["id"] for e in got if e["video_pick"]) or "-"
        print(f"  {c}: {len(got)} [{gs}] picks: {picks}")
    print("dropped/skipped:")
    for eid, reason in skipped:
        print(f"  {eid}: {reason}")


if __name__ == "__main__":
    main()
