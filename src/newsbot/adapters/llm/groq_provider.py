import json
import time

import openai

from newsbot.adapters.llm.openai_compatible_provider import OpenAICompatibleJSONProvider
from newsbot.application.interfaces.llm_provider import LLMProviderError

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
KEY_COOLDOWN_SECONDS = 300.0


class GroqLLMProvider(OpenAICompatibleJSONProvider):
    """Rotates across one or more Groq API keys.

    Groq's free-tier token-per-day cap is per-organization, not per-key, so
    this only helps when the keys belong to separate accounts. On a 429 the
    offending key is put on a cooldown and the same request is retried
    immediately against the next key, instead of failing the whole call.
    """

    provider_label = "Groq"

    def __init__(self, api_keys: list[str], model: str) -> None:
        if not api_keys:
            raise ValueError("GroqLLMProvider requires at least one API key")
        self._model = model
        self._clients = [openai.AsyncOpenAI(api_key=key, base_url=GROQ_BASE_URL) for key in api_keys]
        self._cooldown_until = [0.0] * len(self._clients)
        self._rotor = 0

    async def _call(self, system: str, user_message: str) -> dict:
        n = len(self._clients)
        now = time.monotonic()
        order = [(self._rotor + i) % n for i in range(n)]
        any_available = any(self._cooldown_until[i] <= now for i in order)
        last_error: LLMProviderError | None = None

        for idx in order:
            if any_available and self._cooldown_until[idx] > now:
                continue

            try:
                response = await self._clients[idx].chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                )
            except openai.APIStatusError as exc:
                if exc.status_code == 429:
                    self._cooldown_until[idx] = now + KEY_COOLDOWN_SECONDS
                    last_error = LLMProviderError(str(exc), retryable=True)
                    continue
                retryable = exc.status_code >= 500
                raise LLMProviderError(str(exc), retryable=retryable) from exc
            except openai.APIConnectionError as exc:
                last_error = LLMProviderError(str(exc), retryable=True)
                continue

            self._rotor = (idx + 1) % n
            content = response.choices[0].message.content
            if content is None:
                raise LLMProviderError(f"{self.provider_label} response contained no content", retryable=False)
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMProviderError(
                    f"{self.provider_label} returned invalid JSON: {exc}", retryable=False
                ) from exc

        raise last_error or LLMProviderError(f"{self.provider_label}: all API keys unavailable", retryable=True)

    async def aclose(self) -> None:
        for client in self._clients:
            await client.close()
