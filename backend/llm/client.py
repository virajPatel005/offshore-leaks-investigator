"""One OpenAI-compatible chat wrapper switched by LLM_PROVIDER / LLM_MODEL.

Keys stay in environment variables and are never printed, logged or
returned. Call count is capped per run via MAX_LLM_CALLS_PER_RUN.
"""
import os

from dotenv import load_dotenv

load_dotenv()

PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
}


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
        self._client = OpenAI(base_url=base_url, api_key=api_key, **extra)
        self.provider = provider
        self.model = model or os.getenv("LLM_MODEL", "")
        if not self.model:
            raise RuntimeError("LLM_MODEL is not set")
        self.max_calls = int(max_calls if max_calls is not None
                             else os.getenv("MAX_LLM_CALLS_PER_RUN", "8"))
        self.calls = 0
        self.timeout = 60

    def chat(self, messages, tools=None, tool_choice="auto"):
        """One chat completion; raises RuntimeError once the budget is spent."""
        if self.calls >= self.max_calls:
            raise RuntimeError(f"LLM call budget exhausted ({self.max_calls})")
        self.calls += 1
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return self._client.chat.completions.create(timeout=self.timeout,
                                                      **kwargs).choices[0].message
