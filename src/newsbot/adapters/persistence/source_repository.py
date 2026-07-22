from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.models_orm import SourceORM
from newsbot.domain.models import Source


def _to_domain(row: SourceORM) -> Source:
    return Source(
        id=row.id,
        name=row.name,
        source_type=row.source_type,
        url=row.url,
        category=row.category,
        trust_weight=row.trust_weight,
        is_active=row.is_active,
        last_polled_at=row.last_polled_at,
    )


class SqlSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[Source]:
        result = await self._session.execute(select(SourceORM).where(SourceORM.is_active.is_(True)))
        return [_to_domain(row) for row in result.scalars().all()]

    async def mark_polled(self, source_id, when: datetime) -> None:
        await self._session.execute(
            update(SourceORM).where(SourceORM.id == source_id).values(last_polled_at=when)
        )

    async def get_by_id(self, source_id) -> Source | None:
        row = await self._session.get(SourceORM, source_id)
        return _to_domain(row) if row else None
