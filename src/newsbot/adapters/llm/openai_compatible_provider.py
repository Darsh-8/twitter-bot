import json

import openai
import pydantic

from newsbot.adapters.llm.base import (
    IMPORTANCE_SYSTEM_PROMPT,
    TWEET_SYSTEM_PROMPT,
    VERIFICATION_SYSTEM_PROMPT,
    format_articles_context,
    format_story_context,
)
from newsbot.application.dto import (
    ArticleContext,
    CouncilVoteResult,
    ImportanceResult,
    StoryContext,
    TweetDraftResult,
    VerificationResult,
)
from newsbot.application.interfaces.llm_provider import LLMProviderError

# Shared by any OpenAI-compatible endpoint that doesn't support OpenAI's strict
# json_schema mode (only the looser response_format={"type": "json_object"}), so the
# exact shape is spelled out in-prompt instead and validated client-side via Pydantic.
IMPORTANCE_JSON_INSTRUCTIONS = (
    "\n\nRespond with ONLY a JSON object matching this shape, no other text:\n"
    '{"importance_score": <0-1 float>, "category": <string>, "is_breaking": <bool>, "reasoning": <string>}'
)
VERIFICATION_JSON_INSTRUCTIONS = (
    "\n\nRespond with ONLY a JSON object matching this shape, no other text:\n"
    '{"same_event": <bool>, "confidence_adjustment": <-1 to 1 float>, "reasoning": <string>}'
)
TWEET_JSON_INSTRUCTIONS = (
    "\n\nRespond with ONLY a JSON object matching this shape, no other text:\n"
    '{"text": <string>, "style": <string>, "thread_recommended": <bool>, "reasoning": <string>}'
)
COUNCIL_JSON_INSTRUCTIONS = (
    "\n\nRespond with ONLY a JSON object matching this shape, no other text:\n"
    '{"approve": <bool>, "reasoning": <string>}'
)


class OpenAICompatibleJSONProvider:
    """Base for OpenAI-Chat-Completions-compatible providers using prompt-driven JSON output."""

    provider_label = "LLM provider"

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def _call(self, system: str, user_message: str) -> dict:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
            )
        except openai.APIStatusError as exc:
            retryable = exc.status_code >= 500 or exc.status_code == 429
            raise LLMProviderError(str(exc), retryable=retryable) from exc
        except openai.APIConnectionError as exc:
            raise LLMProviderError(str(exc), retryable=True) from exc

        content = response.choices[0].message.content
        if content is None:
            raise LLMProviderError(f"{self.provider_label} response contained no content", retryable=False)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"{self.provider_label} returned invalid JSON: {exc}", retryable=False
            ) from exc

    def _validate(self, model_cls, data: dict):
        try:
            return model_cls.model_validate(data)
        except pydantic.ValidationError as exc:
            raise LLMProviderError(
                f"{self.provider_label} returned a malformed/incomplete response: {exc}", retryable=True
            ) from exc

    async def score_importance(self, story: StoryContext) -> ImportanceResult:
        system = IMPORTANCE_SYSTEM_PROMPT + IMPORTANCE_JSON_INSTRUCTIONS
        data = await self._call(system, format_story_context(story))
        return self._validate(ImportanceResult, data)

    async def verify_corroboration(self, articles: list[ArticleContext]) -> VerificationResult:
        system = VERIFICATION_SYSTEM_PROMPT + VERIFICATION_JSON_INSTRUCTIONS
        data = await self._call(system, format_articles_context(articles))
        return self._validate(VerificationResult, data)

    async def generate_tweet(self, story: StoryContext, style_hint: str) -> TweetDraftResult:
        system = TWEET_SYSTEM_PROMPT + TWEET_JSON_INSTRUCTIONS
        user_message = f"{format_story_context(story)}\n\nStyle hint: {style_hint}"
        data = await self._call(system, user_message)
        data.setdefault("reasoning", "")
        return self._validate(TweetDraftResult, data)

    async def council_vote(self, story: StoryContext, persona_prompt: str) -> CouncilVoteResult:
        system = persona_prompt + COUNCIL_JSON_INSTRUCTIONS
        data = await self._call(system, format_story_context(story))
        return self._validate(CouncilVoteResult, data)

    async def generate_thread(self, story: StoryContext, style_hint: str) -> list[TweetDraftResult]:
        raise NotImplementedError("Thread generation is a Phase 2 feature")
