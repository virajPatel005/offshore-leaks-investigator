"""Regression check for the ask API contract (uses cached questions: no LLM calls).

Asserts per request: rid echo, question echo, cached flag truthfulness, and
that two different questions in sequence never cross answers.
"""
import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
QA = "What is the strongest recorded connection between GALAXY ASIA LIMITED. and TO.CE.CO LIMITED?"
QB = "Which recorded path links Portcullis TrustNet (BVI) Limited - Nominees with BRAVO ENTERPRISES LIMITED?"


def post(q, rid):
    req = urllib.request.Request(BASE + "/ask",
                                 data=json.dumps({"question": q, "rid": rid}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def stream(q, rid):
    url = BASE + "/ask/stream?" + urllib.parse.urlencode({"question": q, "rid": rid})
    events = []
    with urllib.request.urlopen(url, timeout=120) as r:
        for line in r:
            s = line.decode().strip()
            if s.startswith("data:"):
                events.append(json.loads(s[5:]))
    return events


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        raise SystemExit(1)


a1 = post(QA, "a1")
check("POST QA rid echo", a1.get("rid") == "a1")
check("POST QA question echo", a1.get("question") == QA)
b1 = post(QB, "b1")
check("POST QB rid echo", b1.get("rid") == "b1")
check("POST QB question echo", b1.get("question") == QB)
check("answers differ across questions", (a1.get("answer") or "") != (b1.get("answer") or ""))
a2 = post(QA, "a2")
check("repeat QA cached with matching echo", a2.get("cached") is True and a2.get("question") == QA)
ev = stream(QB, "b2")
fin = [e for e in ev if e.get("type") == "final"]
check("SSE final carries rid", fin and fin[0].get("rid") == "b2")
check("SSE final echo matches QB", fin and fin[0]["result"].get("question") == QB)
print("ALL CHECKS PASSED")
