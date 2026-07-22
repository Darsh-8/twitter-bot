import itertools

from newsbot.application.dto import StoryContext
from newsbot.application.interfaces.llm_provider import LLMProvider
from newsbot.domain.models import Story, TweetDraft

STYLE_HINTS = [
    "analytical",
    "concise/punchy",
    "question-led",
    "contrarian take",
    "technical explanation",
    "comparison to competitors",
    "short observation",
    "breaking news",
    "hot take",
    "hook-led",
]

_style_cycle = itertools.cycle(STYLE_HINTS)

MAX_TWEET_LENGTH = 280


def next_style_hint() -> str:
    return next(_style_cycle)


def enforce_tweet_length(text: str, max_length: int = MAX_TWEET_LENGTH) -> str:
    text = text.strip()
    if len(text) <= max_length:
        return text
    truncated = text[: max_length - 1].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;: ") + "…"


class TweetGenerationService:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def generate(self, story: Story, source_names: list[str]) -> TweetDraft:
        context = StoryContext(
            canonical_title=story.canonical_title,
            summary=story.summary,
            source_count=story.source_count,
            source_names=source_names,
            category_hint=story.category,
        )
        style_hint = "breaking news" if story.is_breaking else next_style_hint()
        draft = await self._llm.generate_tweet(context, style_hint)
        return TweetDraft(
            text=enforce_tweet_length(draft.text),
            style=draft.style,
            thread_recommended=draft.thread_recommended,
            reasoning=draft.reasoning,
        )
