from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.models_orm import RejectionORM
from newsbot.domain.enums import RejectionReason, RejectionStage
from newsbot.domain.models import RejectionRecord


def _to_domain(row: RejectionORM) -> RejectionRecord:
    return RejectionRecord(
        stage=RejectionStage(row.stage),
        reason_code=RejectionReason(row.reason_code),
        story_id=row.story_id,
        raw_article_id=row.raw_article_id,
        detail=row.detail,
        created_at=row.created_at,
    )


class SqlRejectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, rejection: RejectionRecord) -> RejectionRecord:
        row = RejectionORM(
            story_id=rejection.story_id,
            raw_article_id=rejection.raw_article_id,
            stage=rejection.stage.value,
            reason_code=rejection.reason_code.value,
            detail=rejection.detail,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def list_recent(self, limit: int = 100) -> list[RejectionRecord]:
        result = await self._session.execute(
            select(RejectionORM).order_by(RejectionORM.created_at.desc()).limit(limit)
        )
        return [_to_domain(row) for row in result.scalars().all()]
