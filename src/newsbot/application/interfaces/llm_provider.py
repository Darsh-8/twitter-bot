from typing import Protocol

from newsbot.application.dto import (
    ArticleContext,
    CouncilVoteResult,
    ImportanceResult,
    StoryContext,
    TweetDraftResult,
    VerificationResult,
)


class LLMProviderError(Exception):
    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMProvider(Protocol):
    async def score_importance(self, story: StoryContext) -> ImportanceResult: ...

    async def verify_corroboration(
        self, articles: list[ArticleContext]
    ) -> VerificationResult: ...

    async def generate_tweet(self, story: StoryContext, style_hint: str) -> TweetDraftResult: ...

    async def council_vote(self, story: StoryContext, persona_prompt: str) -> CouncilVoteResult: ...

    async def generate_thread(
        self, story: StoryContext, style_hint: str
    ) -> list[TweetDraftResult]:
        """Phase 2: multi-tweet thread generation. Not implemented in the MVP."""
        raise NotImplementedError("Thread generation is a Phase 2 feature")
