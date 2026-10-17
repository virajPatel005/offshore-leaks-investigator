"""One OpenAI-compatible chat wrapper switched by LLM_PROVIDER / LLM_MODEL.

Keys stay in environment variables and are never printed, logged or
returned. Call count is capped per run via MAX_LLM_CALLS_PER_RUN.

Rate-limit guard: the SDK's own retries are disabled (max_retries=0) because
they honour long Retry-After waits and can leave a run hanging for minutes.
Instead every attempt has a hard per-call timeout (LLM_CALL_TIMEOUT_S) and
provider 429s get at most LLM_MAX_ATTEMPTS attempts with a short backoff;
after that a clear LLMRateLimitedError is raised immediately.
"""
import os
import time

from dotenv import load_dotenv

load_dotenv()

PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
}

RATE_LIMIT_MESSAGE = "the language model is rate-limited, try again in a minute"


class LLMError(RuntimeError):
    """Clear, user-facing LLM failure; API and UI show this text as-is."""


class LLMRateLimitedError(LLMError):
    """Provider 429 persisted past the short retry budget."""


class LLMTimeoutError(LLMError):
    """No answer within the per-call timeout, or the provider is unreachable."""


class LLMClient:
    def __init__(self, provider=None, model=None, max_calls=None):
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).strip().lower()
        if provider not in PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {sorted(PROVIDERS)}")
        base_url, key_env = PROVIDERS[provider]
        api_key = os.getenv(key_env, "")
        if not api_key:
            raise RuntimeError(f"{key_env} is not set for provider '{provider}'")
        from openai import OpenAI

        extra = {"default_headers": {"HTTP-Referer": "offshore-investigator",
                                     "X-Title": "offshore-investigator"}} if provider == "openrouter" else {}
        # max_retries=0: our own bounded loop below is the only retry source.
        self._client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0, **extra)
        self.provider = provider
        self.model = model or os.getenv("LLM_MODEL", "")
        if not self.model:
            raise RuntimeError("LLM_MODEL is not set")
        self.max_calls = int(max_calls if max_calls is not None
                             else os.getenv("MAX_LLM_CALLS_PER_RUN", "8"))
        self.calls = 0
        self.timeout = float(os.getenv("LLM_CALL_TIMEOUT_S", "45"))
        self.max_attempts = max(1, int(os.getenv("LLM_MAX_ATTEMPTS", "3")))
        self.backoff_s = (1.0, 2.0)

    def chat(self, messages, tools=None, tool_choice="auto"):
        """One chat completion; raises RuntimeError once the budget is spent.

        Only provider 429s are retried, at most self.max_attempts times, with a
        short sleep between attempts. Timeouts and connection failures raise
        LLMTimeoutError right away; exhausted 429 retries raise
        LLMRateLimitedError carrying the message the API and UI show verbatim.
        """
        if self.calls >= self.max_calls:
            raise RuntimeError(f"LLM call budget exhausted ({self.max_calls})")
        self.calls += 1
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self._client.chat.completions.create(
                    timeout=self.timeout, **kwargs).choices[0].message
            except RateLimitError:
                if attempt < self.max_attempts:
                    time.sleep(self.backoff_s[min(attempt - 1, len(self.backoff_s) - 1)])
            except APITimeoutError as ex:
                raise LLMTimeoutError(
                    f"the language model did not answer within {self.timeout:g}s; try again") from ex
            except APIConnectionError as ex:
                raise LLMTimeoutError(
                    "the language model could not be reached; check the network and try again") from ex
        raise LLMRateLimitedError(RATE_LIMIT_MESSAGE)
