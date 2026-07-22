from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.models_orm import StoryORM, StorySourceORM
from newsbot.domain.enums import StoryStatus
from newsbot.domain.models import Story


def _to_domain(row: StoryORM) -> Story:
    return Story(
        id=row.id,
        canonical_title=row.canonical_title,
        summary=row.summary,
        embedding=list(row.embedding) if row.embedding is not None else None,
        source_count=row.source_count,
        confidence_score=row.confidence_score,
        importance_score=row.importance_score,
        status=StoryStatus(row.status),
        is_breaking=row.is_breaking,
        category=row.category,
        first_seen_at=row.first_seen_at,
        last_updated_at=row.last_updated_at,
    )


class SqlStoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, story: Story) -> Story:
        row = StoryORM(
            canonical_title=story.canonical_title,
            summary=story.summary,
            embedding=story.embedding,
            source_count=story.source_count,
            confidence_score=story.confidence_score,
            importance_score=story.importance_score,
            status=story.status.value,
            is_breaking=story.is_breaking,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get(self, story_id: UUID) -> Story | None:
        row = await self._session.get(StoryORM, story_id)
        return _to_domain(row) if row else None

    async def find_similar(
        self, embedding: list[float], since: datetime, limit: int = 5
    ) -> list[tuple[Story, float]]:
        distance = StoryORM.embedding.cosine_distance(embedding)
        result = await self._session.execute(
            select(StoryORM, distance.label("distance"))
            .where(StoryORM.embedding.is_not(None), StoryORM.last_updated_at >= since)
            .order_by(distance)
            .limit(limit)
        )
        return [(_to_domain(row), 1 - dist) for row, dist in result.all()]

    async def update_status(self, story_id: UUID, status: StoryStatus) -> None:
        await self._session.execute(
            update(StoryORM).where(StoryORM.id == story_id).values(status=status.value)
        )

    async def update_scores(
        self,
        story_id: UUID,
        confidence_score: float | None = None,
        importance_score: float | None = None,
    ) -> None:
        values: dict = {}
        if confidence_score is not None:
            values["confidence_score"] = confidence_score
        if importance_score is not None:
            values["importance_score"] = importance_score
        if values:
            await self._session.execute(update(StoryORM).where(StoryORM.id == story_id).values(**values))

    async def set_breaking(self, story_id: UUID, is_breaking: bool) -> None:
        await self._session.execute(
            update(StoryORM).where(StoryORM.id == story_id).values(is_breaking=is_breaking)
        )

    async def set_category(self, story_id: UUID, category: str) -> None:
        await self._session.execute(
            update(StoryORM).where(StoryORM.id == story_id).values(category=category)
        )

    async def list_by_status(self, status: StoryStatus, limit: int = 50) -> list[Story]:
        result = await self._session.execute(
            select(StoryORM)
            .where(StoryORM.status == status.value)
            .order_by(StoryORM.first_seen_at.asc())
            .limit(limit)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def increment_source_count(
        self, story_id: UUID, similarity_score: float, article_id: UUID
    ) -> None:
        story = await self._session.get(StoryORM, story_id)
        if story is None:
            return
        story.source_count += 1
        self._session.add(
            StorySourceORM(story_id=story_id, raw_article_id=article_id, similarity_score=similarity_score)
        )
