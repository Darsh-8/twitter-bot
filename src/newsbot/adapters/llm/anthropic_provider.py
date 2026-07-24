import anthropic
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

IMPORTANCE_TOOL = {
    "name": "submit_importance_score",
    "description": "Submit the importance scoring result for a news story.",
    "input_schema": {
        "type": "object",
        "properties": {
            "importance_score": {"type": "number", "minimum": 0, "maximum": 1},
            "category": {"type": "string"},
            "is_breaking": {"type": "boolean"},
            "reasoning": {"type": "string"},
        },
        "required": ["importance_score", "category", "is_breaking", "reasoning"],
    },
}

VERIFICATION_TOOL = {
    "name": "submit_verification",
    "description": "Submit the corroboration verification result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "same_event": {"type": "boolean"},
            "confidence_adjustment": {"type": "number", "minimum": -1, "maximum": 1},
            "reasoning": {"type": "string"},
        },
        "required": ["same_event", "confidence_adjustment", "reasoning"],
    },
}

TWEET_TOOL = {
    "name": "submit_tweet",
    "description": "Submit the generated tweet draft.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "style": {"type": "string"},
            "thread_recommended": {"type": "boolean"},
            "reasoning": {"type": "string"},
        },
        "required": ["text", "style", "thread_recommended"],
    },
}

COUNCIL_TOOL = {
    "name": "submit_council_vote",
    "description": "Submit this council member's vote on whether the story is worth posting.",
    "input_schema": {
        "type": "object",
        "properties": {
            "approve": {"type": "boolean"},
            "reasoning": {"type": "string"},
        },
        "required": ["approve", "reasoning"],
    },
}


class AnthropicLLMProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def _call_tool(self, system: str, user_message: str, tool: dict) -> dict:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user_message}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
            )
        except anthropic.APIStatusError as exc:
            retryable = exc.status_code >= 500 or exc.status_code == 429
            raise LLMProviderError(str(exc), retryable=retryable) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMProviderError(str(exc), retryable=True) from exc

        for block in response.content:
            if block.type == "tool_use":
                return block.input
        raise LLMProviderError("Anthropic response contained no tool_use block", retryable=False)

    def _validate(self, model_cls, data: dict):
        try:
            return model_cls.model_validate(data)
        except pydantic.ValidationError as exc:
            raise LLMProviderError(
                f"Anthropic returned a malformed/incomplete response: {exc}", retryable=True
            ) from exc

    async def score_importance(self, story: StoryContext) -> ImportanceResult:
        data = await self._call_tool(
            IMPORTANCE_SYSTEM_PROMPT, format_story_context(story), IMPORTANCE_TOOL
        )
        return self._validate(ImportanceResult, data)

    async def verify_corroboration(self, articles: list[ArticleContext]) -> VerificationResult:
        data = await self._call_tool(
            VERIFICATION_SYSTEM_PROMPT, format_articles_context(articles), VERIFICATION_TOOL
        )
        return self._validate(VerificationResult, data)

    async def generate_tweet(self, story: StoryContext, style_hint: str) -> TweetDraftResult:
        user_message = f"{format_story_context(story)}\n\nStyle hint: {style_hint}"
        data = await self._call_tool(TWEET_SYSTEM_PROMPT, user_message, TWEET_TOOL)
        data.setdefault("reasoning", "")
        return self._validate(TweetDraftResult, data)

    async def council_vote(self, story: StoryContext, persona_prompt: str) -> CouncilVoteResult:
        data = await self._call_tool(persona_prompt, format_story_context(story), COUNCIL_TOOL)
        return self._validate(CouncilVoteResult, data)

    async def generate_thread(self, story: StoryContext, style_hint: str) -> list[TweetDraftResult]:
        raise NotImplementedError("Thread generation is a Phase 2 feature")

    async def aclose(self) -> None:
        await self._client.close()
