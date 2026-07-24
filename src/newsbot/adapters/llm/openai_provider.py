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

IMPORTANCE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "importance_result",
        "schema": {
            "type": "object",
            "properties": {
                "importance_score": {"type": "number"},
                "category": {"type": "string"},
                "is_breaking": {"type": "boolean"},
                "reasoning": {"type": "string"},
            },
            "required": ["importance_score", "category", "is_breaking", "reasoning"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

VERIFICATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "verification_result",
        "schema": {
            "type": "object",
            "properties": {
                "same_event": {"type": "boolean"},
                "confidence_adjustment": {"type": "number"},
                "reasoning": {"type": "string"},
            },
            "required": ["same_event", "confidence_adjustment", "reasoning"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

TWEET_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "tweet_draft",
        "schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "style": {"type": "string"},
                "thread_recommended": {"type": "boolean"},
                "reasoning": {"type": "string"},
            },
            "required": ["text", "style", "thread_recommended", "reasoning"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

COUNCIL_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "council_vote",
        "schema": {
            "type": "object",
            "properties": {
                "approve": {"type": "boolean"},
                "reasoning": {"type": "string"},
            },
            "required": ["approve", "reasoning"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


class OpenAILLMProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def _call(self, system: str, user_message: str, schema: dict) -> dict:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                response_format=schema,
            )
        except openai.APIStatusError as exc:
            retryable = exc.status_code >= 500 or exc.status_code == 429
            raise LLMProviderError(str(exc), retryable=retryable) from exc
        except openai.APIConnectionError as exc:
            raise LLMProviderError(str(exc), retryable=True) from exc

        content = response.choices[0].message.content
        if content is None:
            raise LLMProviderError("OpenAI response contained no content", retryable=False)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(f"OpenAI returned invalid JSON: {exc}", retryable=True) from exc

    def _validate(self, model_cls, data: dict):
        try:
            return model_cls.model_validate(data)
        except pydantic.ValidationError as exc:
            raise LLMProviderError(
                f"OpenAI returned a malformed/incomplete response: {exc}", retryable=True
            ) from exc

    async def score_importance(self, story: StoryContext) -> ImportanceResult:
        data = await self._call(IMPORTANCE_SYSTEM_PROMPT, format_story_context(story), IMPORTANCE_SCHEMA)
        return self._validate(ImportanceResult, data)

    async def verify_corroboration(self, articles: list[ArticleContext]) -> VerificationResult:
        data = await self._call(
            VERIFICATION_SYSTEM_PROMPT, format_articles_context(articles), VERIFICATION_SCHEMA
        )
        return self._validate(VerificationResult, data)

    async def generate_tweet(self, story: StoryContext, style_hint: str) -> TweetDraftResult:
        user_message = f"{format_story_context(story)}\n\nStyle hint: {style_hint}"
        data = await self._call(TWEET_SYSTEM_PROMPT, user_message, TWEET_SCHEMA)
        return self._validate(TweetDraftResult, data)

    async def council_vote(self, story: StoryContext, persona_prompt: str) -> CouncilVoteResult:
        data = await self._call(persona_prompt, format_story_context(story), COUNCIL_SCHEMA)
        return self._validate(CouncilVoteResult, data)

    async def generate_thread(self, story: StoryContext, style_hint: str) -> list[TweetDraftResult]:
        raise NotImplementedError("Thread generation is a Phase 2 feature")

    async def aclose(self) -> None:
        await self._client.close()
