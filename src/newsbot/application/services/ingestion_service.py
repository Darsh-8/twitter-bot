import asyncio
from datetime import datetime, timedelta, timezone

import structlog

from newsbot.application.interfaces.embedder import Embedder
from newsbot.application.interfaces.repositories import ArticleRepository, SourceRepository
from newsbot.application.interfaces.source_client import NewsSourceClient, SourceFetchError
from newsbot.domain.models import Article, Source

logger = structlog.get_logger(__name__)

DEFAULT_MAX_ARTICLE_AGE_DAYS = 7
DEFAULT_MAX_ARTICLES_PER_SOURCE_PER_POLL = 10
DEFAULT_SOURCE_POLL_DELAY_SECONDS = 2.0


class IngestionService:
    def __init__(
        self,
        source_repo: SourceRepository,
        article_repo: ArticleRepository,
        source_client: NewsSourceClient,
        embedder: Embedder,
        max_article_age_days: int = DEFAULT_MAX_ARTICLE_AGE_DAYS,
        max_articles_per_source: int = DEFAULT_MAX_ARTICLES_PER_SOURCE_PER_POLL,
        source_poll_delay_seconds: float = DEFAULT_SOURCE_POLL_DELAY_SECONDS,
    ) -> None:
        self._source_repo = source_repo
        self._article_repo = article_repo
        self._source_client = source_client
        self._embedder = embedder
        self._max_article_age_days = max_article_age_days
        self._max_articles_per_source = max_articles_per_source
        self._source_poll_delay_seconds = source_poll_delay_seconds

    async def poll_all_sources(self) -> dict:
        sources = await self._source_repo.list_active()
        stats = {
            "sources_polled": 0,
            "sources_failed": 0,
            "articles_new": 0,
            "articles_duplicate": 0,
            "articles_too_old": 0,
            "articles_skipped_over_cap": 0,
        }
        for i, source in enumerate(sources):
            if i > 0:
                await asyncio.sleep(self._source_poll_delay_seconds)
            try:
                new_count, dup_count, old_count, skipped_count = await self._poll_source(source)
                stats["articles_new"] += new_count
                stats["articles_duplicate"] += dup_count
                stats["articles_too_old"] += old_count
                stats["articles_skipped_over_cap"] += skipped_count
                stats["sources_polled"] += 1
            except SourceFetchError as exc:
                stats["sources_failed"] += 1
                logger.warning("source_poll_failed", source=source.name, error=str(exc))
        return stats

    async def _poll_source(self, source: Source) -> tuple[int, int, int, int]:
        articles = await self._source_client.fetch(source)
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._max_article_age_days)

        recent_articles = []
        old_count = 0
        for article in articles:
            if article.published_at is not None and article.published_at < cutoff:
                old_count += 1
            else:
                recent_articles.append(article)

        recent_articles.sort(
            key=lambda a: a.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True
        )
        capped_articles = recent_articles[: self._max_articles_per_source]
        skipped_count = len(recent_articles) - len(capped_articles)

        new_count = 0
        dup_count = 0
        for article in capped_articles:
            if await self._article_repo.exists(source.id, article.external_id):
                dup_count += 1
                continue
            saved = await self._article_repo.add(article)
            embedding = self._embedder.embed(f"{article.title}\n{article.summary or ''}")
            await self._article_repo.update_embedding(saved.id, embedding)
            new_count += 1
            logger.info("article_ingested", source=source.name, title=article.title, url=article.url)

        await self._source_repo.mark_polled(source.id, datetime.now(timezone.utc))
        return new_count, dup_count, old_count, skipped_count
