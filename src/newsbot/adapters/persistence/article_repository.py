from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.models_orm import RawArticleORM
from newsbot.domain.models import Article


def _to_domain(row: RawArticleORM) -> Article:
    return Article(
        id=row.id,
        source_id=row.source_id,
        external_id=row.external_id,
        title=row.title,
        url=row.url,
        summary=row.summary,
        content=row.content,
        published_at=row.published_at,
        fetched_at=row.fetched_at,
        embedding=list(row.embedding) if row.embedding is not None else None,
        story_id=row.story_id,
        raw_payload=row.raw_payload,
    )


class SqlArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, source_id: UUID, external_id: str) -> bool:
        result = await self._session.execute(
            select(RawArticleORM.id).where(
                RawArticleORM.source_id == source_id,
                RawArticleORM.external_id == external_id,
            )
        )
        return result.first() is not None

    async def add(self, article: Article) -> Article:
        row = RawArticleORM(
            source_id=article.source_id,
            external_id=article.external_id,
            title=article.title,
            summary=article.summary,
            content=article.content,
            url=article.url,
            published_at=article.published_at,
            raw_payload=article.raw_payload,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def update_embedding(self, article_id: UUID, embedding: list[float]) -> None:
        await self._session.execute(
            update(RawArticleORM).where(RawArticleORM.id == article_id).values(embedding=embedding)
        )

    async def list_unclustered(self, since: datetime) -> list[Article]:
        result = await self._session.execute(
            select(RawArticleORM).where(
                RawArticleORM.story_id.is_(None),
                RawArticleORM.embedding.is_not(None),
                RawArticleORM.fetched_at >= since,
            )
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def attach_to_story(self, article_id: UUID, story_id: UUID) -> None:
        await self._session.execute(
            update(RawArticleORM).where(RawArticleORM.id == article_id).values(story_id=story_id)
        )

    async def list_by_story(self, story_id: UUID) -> list[Article]:
        result = await self._session.execute(
            select(RawArticleORM).where(RawArticleORM.story_id == story_id)
        )
        return [_to_domain(row) for row in result.scalars().all()]
