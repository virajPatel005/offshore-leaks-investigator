"""FastAPI front end for the investigator agent (local only, 127.0.0.1).

POST /ask runs the agent; GET /ask/stream replays trace steps as SSE;
GET /health checks FalkorDB. Demo answers are cached in runs/cache.json.
Rate limit and daily LLM cap come from env; errors are structured, never
tracebacks.
"""
import asyncio
import json
import os
import sys
import time
from collections import deque
from datetime import date
from typing import Literal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from backend.agent.agent import arun

REQUEST_TIMEOUT_S = int(os.getenv("ASK_TIMEOUT_S", "300"))
RATE_PER_MIN = int(os.getenv("ASK_RATE_PER_MIN", "20"))
DAILY_CAP = int(os.getenv("DAILY_LLM_CAP", "100"))
USAGE_FILE = "runs/llm_usage.json"
CACHE_FILE = "runs/cache.json"

app = FastAPI(title="offshore-investigator")
_hits = deque()


class AskBody(BaseModel):
    question: str
    rid: str | None = None
    pins: dict[str, str] | None = None


class ConnectBody(BaseModel):
    a: str
    b: str
    mode: Literal["strongest", "shared"]


def norm(q):
    return " ".join((q or "").casefold().split())


def clean_pins(pins):
    """Pins = {name: node_id} chosen from an ambiguity list; ids only (D13)."""
    if not pins:
        return None
    out = {str(k): str(v) for k, v in pins.items() if k and v}
    return out or None


def cache_key(question, pins):
    """Plain question text when unpinned (old cache stays valid); pinned runs
    get their own key so the chosen record is part of the identity. Non-default
    graphs get a name prefix so one graph's answer is never served for another
    (the default graph keeps the shipped keys readable as-is)."""
    k = norm(question)
    if pins:
        k += " |pins " + " ".join(f"{norm(n)}={pins[n]}" for n in sorted(pins, key=norm))
    graph = os.getenv("GRAPH_NAME", "offshore")
    if graph != "offshore":
        k = f"{graph}|{k}"
    return k


def _cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _usage():
    try:
        with open(USAGE_FILE, encoding="utf-8") as f:
            u = json.load(f)
    except (OSError, ValueError):
        u = {}
    if u.get("date") != date.today().isoformat():
        u = {"date": date.today().isoformat(), "calls": 0}
    return u


def _check_limits():
    now = time.time()
    while _hits and _hits[0] < now - 60:
        _hits.popleft()
    if len(_hits) >= RATE_PER_MIN:
        raise HTTPException(429, "rate limit: too many questions per minute")
    if _usage().get("calls", 0) >= DAILY_CAP:
        raise HTTPException(429, "daily LLM call budget spent")


async def _answer(question, on_step=None, rid=None, fresh=False, pins=None):
    """One source of truth per request: every response echoes rid + question.

    Cache stores the question text but never a rid; fresh=True serves live
    even on a cache hit (still writing the cache afterwards). Pins select a
    specific record for an ambiguous name and become part of the cache key.
    """
    pins = clean_pins(pins)
    key = cache_key(question, pins)
    cache = _cache()
    if not fresh and key in cache:
        res = dict(cache[key])
        res["cached"] = True
        res["rid"] = rid
        res["question"] = question
        res.setdefault("pins", pins or {})
        return res
    _check_limits()
    _hits.append(time.time())
    try:
        res = await asyncio.wait_for(arun(question, on_step=on_step, pins=pins), timeout=REQUEST_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise HTTPException(504, "agent run timed out")
    except RuntimeError as ex:
        raise HTTPException(429, str(ex))  # LLM budget spent mid-run
    except Exception:
        raise HTTPException(502, "agent run failed")
    u = _usage()
    u["calls"] = u.get("calls", 0) + int(res.get("llm_calls", 0))
    os.makedirs("runs", exist_ok=True)
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(u, f)
    if res.get("answer"):
        res["question"] = question
        cache[key] = {k: v for k, v in res.items() if k != "rid"}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    res["cached"] = False
    res["rid"] = rid
    res["question"] = question
    res["pins"] = pins or {}
    return res


@app.get("/health")
def health():
    try:
        from falkordb import FalkorDB

        db = FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"),
                      port=int(os.getenv("FALKORDB_PORT", "6379")))
        graph_name = os.getenv("GRAPH_NAME", "offshore")
        n = db.select_graph(graph_name).query(
            "MATCH (n) RETURN count(n) LIMIT 1").result_set[0][0]
        return {"status": "up", "graph": graph_name, "nodes": n}
    except Exception as ex:
        raise HTTPException(503, f"graph unreachable: {type(ex).__name__}")


@app.get("/neighbors")
def neighbors(node_id: str, hub_threshold: int = 1000, limit: int = 25, allow_hub: bool = False):
    """Read-only graph expansion for the UI; no LLM involved."""
    if not node_id or not node_id.strip():
        raise HTTPException(400, "node_id required")
    from backend.graph.neighbors import get_neighbors

    try:
        return get_neighbors(node_id, hub_threshold=hub_threshold, limit=limit, allow_hub=allow_hub)
    except Exception:
        raise HTTPException(502, "neighbor expansion failed")


@app.post("/connect")
def connect(body: ConnectBody):
    """Two nodes picked in the UI graph -> Q6/Q8 card. Deterministic, no LLM."""
    from backend.agent.actions import shared_action, strongest_action

    a, b = body.a.strip(), body.b.strip()
    if not a or not b:
        raise HTTPException(400, "both node ids required")
    if a == b:
        raise HTTPException(400, "pick two different nodes")
    fn = strongest_action if body.mode == "strongest" else shared_action
    try:
        res = fn(a, b)
    except Exception:
        raise HTTPException(502, "graph action failed")
    if res.get("error"):
        raise HTTPException(404, res["error"])
    return res


@app.post("/ask")
async def ask(body: AskBody):
    if not body.question or not body.question.strip():
        raise HTTPException(400, "empty question")
    return await _answer(body.question, rid=body.rid, pins=body.pins)


@app.get("/ask/stream")
async def ask_stream(question: str, rid: str | None = None, fresh: bool = False,
                     pins: str | None = None):
    if not question or not question.strip():
        raise HTTPException(400, "empty question")
    try:
        pin_map = json.loads(pins) if pins else None
    except ValueError:
        raise HTTPException(400, "pins must be a JSON object")

    async def gen():
        queue, loop = asyncio.Queue(), asyncio.get_running_loop()
        result, error = {}, None

        async def runner():
            nonlocal result, error
            try:
                result = await _answer(question, fresh=fresh, pins=pin_map,
                                       on_step=lambda e: loop.call_soon_threadsafe(queue.put_nowait, e),
                                       rid=rid)
            except HTTPException as ex:
                error = ex
            except Exception:
                error = HTTPException(502, "agent run failed")
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(runner())
        while True:
            entry = await queue.get()
            if entry is None:
                break
            yield f"data: {json.dumps({'type': 'step', 'rid': rid, 'step': entry})}\n\n"
        await task
        if error is not None:
            yield f"data: {json.dumps({'type': 'error', 'rid': rid, 'detail': error.detail})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'final', 'rid': rid, 'result': result})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/intro", include_in_schema=False)
def intro_page():
    return FileResponse("web/intro.html")


@app.get("/outro", include_in_schema=False)
def outro_page():
    return FileResponse("web/outro.html")


app.mount("/", StaticFiles(directory="web", html=True), name="web")
