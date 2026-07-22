import re
from datetime import datetime, timezone
from uuid import uuid4

from newsbot.application.dto import ImportanceResult, TweetDraftResult, VerificationResult
from newsbot.domain.enums import StoryStatus
from newsbot.domain.models import Article, PostedTweet, RejectionRecord, Source, Story

_WORD_RE = re.compile(r"[a-z0-9]+")
_VOCAB = [
    "openai",
    "gpt",
    "6",
    "reasoning",
    "coding",
    "code",
    "launch",
    "model",
    "flagship",
    "unrelated",
    "minor",
    "update",
]


class FakeEmbedder:
    """Deterministic bag-of-words embedder so semantically similar fixture text clusters together."""

    def embed(self, text: str) -> list[float]:
        words = set(_WORD_RE.findall(text.lower()))
        return [1.0 if term in words else 0.0 for term in _VOCAB]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemorySourceRepository:
    def __init__(self, sources: list[Source]):
        self._sources = {s.id: s for s in sources}

    async def list_active(self) -> list[Source]:
        return [s for s in self._sources.values() if s.is_active]

    async def mark_polled(self, source_id, when) -> None:
        self._sources[source_id].last_polled_at = when

    async def get_by_id(self, source_id):
        return self._sources.get(source_id)


class InMemoryArticleRepository:
    def __init__(self):
        self._articles: dict = {}

    async def exists(self, source_id, external_id) -> bool:
        return any(
            a.source_id == source_id and a.external_id == external_id for a in self._articles.values()
        )

    async def add(self, article: Article) -> Article:
        article.id = uuid4()
        article.fetched_at = datetime.now(timezone.utc)
        self._articles[article.id] = article
        return article

    async def update_embedding(self, article_id, embedding) -> None:
        self._articles[article_id].embedding = embedding

    async def list_unclustered(self, since) -> list[Article]:
        return [a for a in self._articles.values() if a.story_id is None]

    async def attach_to_story(self, article_id, story_id) -> None:
        self._articles[article_id].story_id = story_id

    async def list_by_story(self, story_id) -> list[Article]:
        return [a for a in self._articles.values() if a.story_id == story_id]


class InMemoryStoryRepository:
    def __init__(self):
        self._stories: dict = {}

    async def add(self, story: Story) -> Story:
        story.id = uuid4()
        self._stories[story.id] = story
        return story

    async def get(self, story_id):
        return self._stories.get(story_id)

    async def find_similar(self, embedding, since, limit=5):
        scored = [(s, _cosine(embedding, s.embedding)) for s in self._stories.values() if s.embedding]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    async def update_status(self, story_id, status) -> None:
        self._stories[story_id].status = status

    async def update_scores(self, story_id, confidence_score=None, importance_score=None) -> None:
        if confidence_score is not None:
            self._stories[story_id].confidence_score = confidence_score
        if importance_score is not None:
            self._stories[story_id].importance_score = importance_score

    async def set_breaking(self, story_id, is_breaking) -> None:
        self._stories[story_id].is_breaking = is_breaking

    async def set_category(self, story_id, category) -> None:
        self._stories[story_id].category = category

    async def list_by_status(self, status, limit=50) -> list[Story]:
        return [s for s in self._stories.values() if s.status == status][:limit]

    async def increment_source_count(self, story_id, similarity_score, article_id) -> None:
        self._stories[story_id].source_count += 1


class InMemoryTweetRepository:
    def __init__(self):
        self.tweets: list[PostedTweet] = []

    async def add(self, tweet: PostedTweet) -> PostedTweet:
        tweet.id = uuid4()
        self.tweets.append(tweet)
        return tweet

    async def count_since(self, since) -> int:
        return len([t for t in self.tweets if t.posted_at and t.posted_at >= since])

    async def last_posted_at(self):
        posted = [t.posted_at for t in self.tweets if t.posted_at]
        return max(posted) if posted else None

    async def list_recent(self, limit=50):
        return self.tweets[-limit:]


class InMemoryRejectionRepository:
    def __init__(self):
        self.rejections: list[RejectionRecord] = []

    async def add(self, rejection: RejectionRecord) -> RejectionRecord:
        self.rejections.append(rejection)
        return rejection

    async def list_recent(self, limit=100):
        return self.rejections[-limit:]


class FakeLLMProvider:
    """Canned LLM responses: high importance for GPT-6, low for anything else."""

    async def verify_corroboration(self, articles) -> VerificationResult:
        return VerificationResult(same_event=True, confidence_adjustment=0.1, reasoning="fake: same event")

    async def score_importance(self, story) -> ImportanceResult:
        if "gpt-6" in story.canonical_title.lower() or "gpt" in story.canonical_title.lower():
            return ImportanceResult(
                importance_score=0.95, category="model_release", is_breaking=True, reasoning="fake: major release"
            )
        return ImportanceResult(
            importance_score=0.1, category="minor_update", is_breaking=False, reasoning="fake: minor"
        )

    async def generate_tweet(self, story, style_hint) -> TweetDraftResult:
        return TweetDraftResult(
            text=f"OpenAI just released GPT-6. Big jump in reasoning and coding performance. ({style_hint})",
            style=style_hint,
            thread_recommended=False,
            reasoning="fake tweet",
        )

    async def generate_thread(self, story, style_hint):
        raise NotImplementedError
