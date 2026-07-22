from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.models_orm import CouncilVoteORM
from newsbot.domain.models import CouncilVoteRecord


def _to_domain(row: CouncilVoteORM) -> CouncilVoteRecord:
    return CouncilVoteRecord(
        id=row.id,
        story_id=row.story_id,
        persona_name=row.persona_name,
        approve=row.approve,
        reasoning=row.reasoning,
        created_at=row.created_at,
    )


class SqlCouncilVoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, vote: CouncilVoteRecord) -> CouncilVoteRecord:
        row = CouncilVoteORM(
            story_id=vote.story_id,
            persona_name=vote.persona_name,
            approve=vote.approve,
            reasoning=vote.reasoning,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def list_for_story(self, story_id: UUID) -> list[CouncilVoteRecord]:
        result = await self._session.execute(
            select(CouncilVoteORM)
            .where(CouncilVoteORM.story_id == story_id)
            .order_by(CouncilVoteORM.created_at.asc())
        )
        return [_to_domain(row) for row in result.scalars().all()]
