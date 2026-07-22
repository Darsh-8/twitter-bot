from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from newsbot.application.services.ingestion_service import IngestionService
from newsbot.domain.models import Article, Source


class FakeSourceRepository:
    def __init__(self, sources):
        self._sources = sources

    async def list_active(self):
        return self._sources

    async def mark_polled(self, source_id, when):
        pass


class FakeArticleRepository:
    def __init__(self):
        self.added = []

    async def exists(self, source_id, external_id):
        return False

    async def add(self, article):
        article.id = uuid4()
        self.added.append(article)
        return article

    async def update_embedding(self, article_id, embedding):
        pass


class FakeSourceClient:
    def __init__(self, articles):
        self._articles = articles

    async def fetch(self, source):
        return self._articles


class FakeEmbedder:
    def embed(self, text):
        return [0.0]

    def embed_batch(self, texts):
        return [[0.0] for _ in texts]


def _article(source_id, age_days: float | None):
    published_at = (
        None if age_days is None else datetime.now(timezone.utc) - timedelta(days=age_days)
    )
    return Article(
        id=None,
        source_id=source_id,
        external_id=f"id-{age_days}",
        title="Some story",
        url="https://example.com",
        published_at=published_at,
    )


@pytest.mark.asyncio
async def test_articles_older_than_max_age_are_skipped():
    source = Source(id=uuid4(), name="Feed", source_type="rss", url="", category="tech_media")
    articles = [_article(source.id, age_days=1), _article(source.id, age_days=10)]
    article_repo = FakeArticleRepository()
    service = IngestionService(
        FakeSourceRepository([source]),
        article_repo,
        FakeSourceClient(articles),
        FakeEmbedder(),
        max_article_age_days=7,
    )

    stats = await service.poll_all_sources()

    assert stats["articles_new"] == 1
    assert stats["articles_too_old"] == 1
    assert len(article_repo.added) == 1


@pytest.mark.asyncio
async def test_articles_without_published_date_are_kept():
    source = Source(id=uuid4(), name="Feed", source_type="rss", url="", category="tech_media")
    articles = [_article(source.id, age_days=None)]
    article_repo = FakeArticleRepository()
    service = IngestionService(
        FakeSourceRepository([source]),
        article_repo,
        FakeSourceClient(articles),
        FakeEmbedder(),
        max_article_age_days=7,
    )

    stats = await service.poll_all_sources()

    assert stats["articles_new"] == 1
    assert stats["articles_too_old"] == 0


@pytest.mark.asyncio
async def test_articles_beyond_per_source_cap_are_skipped():
    source = Source(id=uuid4(), name="arXiv cs.AI", source_type="rss", url="", category="research")
    # 15 recent articles, but the cap is 5 -> only the 5 newest should be ingested
    articles = [_article(source.id, age_days=i * 0.1) for i in range(15)]
    article_repo = FakeArticleRepository()
    service = IngestionService(
        FakeSourceRepository([source]),
        article_repo,
        FakeSourceClient(articles),
        FakeEmbedder(),
        max_article_age_days=7,
        max_articles_per_source=5,
    )

    stats = await service.poll_all_sources()

    assert stats["articles_new"] == 5
    assert stats["articles_skipped_over_cap"] == 10
    assert len(article_repo.added) == 5


@pytest.mark.asyncio
async def test_per_source_cap_keeps_the_newest_articles():
    source = Source(id=uuid4(), name="Feed", source_type="rss", url="", category="tech_media")
    newest = _article(source.id, age_days=0.01)
    oldest = _article(source.id, age_days=6.9)
    article_repo = FakeArticleRepository()
    service = IngestionService(
        FakeSourceRepository([source]),
        article_repo,
        FakeSourceClient([oldest, newest]),
        FakeEmbedder(),
        max_article_age_days=7,
        max_articles_per_source=1,
    )

    await service.poll_all_sources()

    assert len(article_repo.added) == 1
    assert article_repo.added[0] is newest
