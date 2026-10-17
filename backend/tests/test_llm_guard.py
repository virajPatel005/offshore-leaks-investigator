"""Rate-limit guard tests with a fake failing client. No real LLM calls.

Covers: the client retry cap + clear error, the API mapping (POST /ask),
the SSE error event (/ask/stream), and the grounding checker samples that
back the prompt rule (ids/names only from tool results).

Run from the repo root:  .venv/bin/python backend/tests/test_llm_guard.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx
from openai import APITimeoutError, RateLimitError

import backend.agent.agent as agent_mod
from backend.agent.agent import _ground
from backend.llm.client import LLMClient, LLMRateLimitedError, LLMTimeoutError, RATE_LIMIT_MESSAGE

FAILS = []
CHECKS = 0


def check(name, cond):
    global CHECKS
    CHECKS += 1
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def _rate_limit_error():
    req = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    return RateLimitError("429 from fake provider", response=httpx.Response(429, request=req),
                          body=None)


def _timeout_error():
    req = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    return APITimeoutError(request=req)


class FakeOpenAI:
    """Mimics just enough of the OpenAI client for LLMClient.chat()."""

    def __init__(self, exc):
        self.exc = exc
        self.attempts = 0
        self.chat = self

        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.attempts += 1
                raise outer.exc

        self.chat.completions = _Completions()


def make_client(exc):
    c = LLMClient.__new__(LLMClient)  # bypass __init__: no env, no keys, no network
    c.calls = 0
    c.max_calls = 8
    c.model = "fake"
    c.timeout = 45
    c.max_attempts = 3
    c.backoff_s = (0.05, 0.05)  # short for the test; production default is (1.0, 2.0)
    c._client = FakeOpenAI(exc)
    return c


def test_client_retry_cap():
    c = make_client(_rate_limit_error())
    t0 = time.monotonic()
    try:
        c.chat([{"role": "user", "content": "hi"}])
        check("rate-limit raises", False)
    except LLMRateLimitedError as ex:
        elapsed = time.monotonic() - t0
        check("rate-limit raises LLMRateLimitedError", True)
        check("rate-limit message is the clear text", str(ex) == RATE_LIMIT_MESSAGE)
        check(f"rate-limit attempts capped at 3 (got {c._client.attempts})", c._client.attempts == 3)
        check(f"rate-limit fails fast ({elapsed:.2f}s < 2s)", elapsed < 2.0)


def test_client_timeout_mapping():
    c = make_client(_timeout_error())
    try:
        c.chat([{"role": "user", "content": "hi"}])
        check("timeout raises", False)
    except LLMTimeoutError as ex:
        check("timeout maps to LLMTimeoutError", "did not answer within" in str(ex))
        check("timeout is not retried", c._client.attempts == 1)
    except LLMRateLimitedError:
        check("timeout maps to LLMTimeoutError", False)


class FakeLLM:
    """Stands in for backend.agent.agent.LLMClient; raises before any network."""

    def __init__(self):
        self.calls = 0
        self.max_calls = 8
        self.provider = "fake"

    def chat(self, *a, **k):
        self.calls += 1
        raise LLMRateLimitedError(RATE_LIMIT_MESSAGE)


def patch_agent_llm():
    agent_mod.LLMClient = FakeLLM


async def test_api_and_stream():
    transport = httpx.ASGITransport(app=agent_mod_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/ask", json={"question": "guard test ask unique 83741", "rid": "t1"})
        check(f"POST /ask status 429 (got {r.status_code})", r.status_code == 429)
        check("POST /ask detail is the clear message",
              r.json().get("detail") == RATE_LIMIT_MESSAGE)
        async with client.stream("GET", "/ask/stream",
                                 params={"question": "guard test stream unique 83742", "rid": "t2"}) as s:
            events = []
            async for line in s.aiter_lines():
                if line.startswith("data:"):
                    import json as _json
                    events.append(_json.loads(line[5:]))
        errors = [e for e in events if e.get("type") == "error"]
        finals = [e for e in events if e.get("type") == "final"]
        check("SSE emits exactly one error event", len(errors) == 1)
        check("SSE error carries the clear message",
              errors and errors[0].get("detail") == RATE_LIMIT_MESSAGE)
        check("SSE emits no final result", not finals)


def agent_mod_app():
    from backend.app.main import app
    return app


def test_grounding_samples():
    evidence = [{"path": {"nodes": [{"node_id": "108197", "name": "MIRALEY LTD.", "degree_core": 2}],
                          "edges": [{"rel_type": "officer_of", "link": "Director"}]}}]
    _, g1 = _ground('MIRALEY LTD. (node_id 108197) is linked by officer_of.', evidence, "q")
    check("grounding passes a clean answer", not g1["unknown_ids"] and not g1["stripped"])
    ans, g2 = _ground("Maybe node 999999 is involved.", evidence, "q")
    check("grounding flags + strips an invented id",
          bool(g2["unknown_ids"]) and g2["stripped"] and "999999" not in ans)


class SlowLLM:
    """Sleeps inside the worker thread; the request timeout must cancel the run."""

    def __init__(self):
        self.calls = 0
        self.max_calls = 8
        self.provider = "fake"

    def chat(self, *a, **k):
        time.sleep(4)
        raise RuntimeError("never reached: the run must have been cancelled")


async def test_timeout_cancels_run():
    import backend.app.main as main_mod

    old = main_mod.REQUEST_TIMEOUT_S
    main_mod.REQUEST_TIMEOUT_S = 1
    agent_mod.LLMClient = SlowLLM
    try:
        transport = httpx.ASGITransport(app=main_mod.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            t0 = time.monotonic()
            r = await client.post("/ask", json={"question": "guard test timeout unique 83743",
                                                "rid": "t3"})
            elapsed = time.monotonic() - t0
        check(f"timeout gives 504 (got {r.status_code})", r.status_code == 504)
        check(f"timeout returns fast ({elapsed:.2f}s < 3s)", elapsed < 3.0)
        check("timeout detail is clear", "timed out" in str(r.json().get("detail", "")))
    finally:
        main_mod.REQUEST_TIMEOUT_S = old
        agent_mod.LLMClient = FakeLLM


def main():
    test_client_retry_cap()
    test_client_timeout_mapping()
    patch_agent_llm()
    asyncio.run(test_api_and_stream())
    asyncio.run(test_timeout_cancels_run())
    test_grounding_samples()
    print(f"\n{CHECKS - len(FAILS)}/{CHECKS} checks passed" if FAILS else f"\nALL {CHECKS} CHECKS PASSED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
