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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
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


def norm(q):
    return " ".join((q or "").casefold().split())


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


async def _answer(question, on_step=None):
    key = norm(question)
    cache = _cache()
    if key in cache:
        res = dict(cache[key])
        res["cached"] = True
        return res
    _check_limits()
    _hits.append(time.time())
    try:
        res = await asyncio.wait_for(arun(question, on_step=on_step), timeout=REQUEST_TIMEOUT_S)
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
        cache[key] = res
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    res["cached"] = False
    return res


@app.get("/health")
def health():
    try:
        from falkordb import FalkorDB

        db = FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"),
                      port=int(os.getenv("FALKORDB_PORT", "6379")))
        n = db.select_graph(os.getenv("GRAPH_NAME", "offshore")).query(
            "MATCH (n) RETURN count(n) LIMIT 1").result_set[0][0]
        return {"status": "up", "nodes": n}
    except Exception as ex:
        raise HTTPException(503, f"graph unreachable: {type(ex).__name__}")


@app.post("/ask")
async def ask(body: AskBody):
    if not body.question or not body.question.strip():
        raise HTTPException(400, "empty question")
    return await _answer(body.question)


@app.get("/ask/stream")
async def ask_stream(question: str):
    if not question or not question.strip():
        raise HTTPException(400, "empty question")
    key = norm(question)
    if key in _cache():
        async def cached():
            yield f"data: {json.dumps({'type': 'final', 'result': _cache()[key] | {'cached': True}})}\n\n"
        return StreamingResponse(cached(), media_type="text/event-stream")

    async def gen():
        queue, loop = asyncio.Queue(), asyncio.get_running_loop()
        result, error = {}, None

        async def runner():
            nonlocal result, error
            try:
                result = await _answer(question, on_step=lambda e: loop.call_soon_threadsafe(queue.put_nowait, e))
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
            yield f"data: {json.dumps({'type': 'step', 'step': entry})}\n\n"
        await task
        if error is not None:
            yield f"data: {json.dumps({'type': 'error', 'detail': error.detail})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'final', 'result': result})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="web", html=True), name="web")
