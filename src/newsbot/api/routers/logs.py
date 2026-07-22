from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.council_vote_repository import SqlCouncilVoteRepository
from newsbot.adapters.persistence.rejection_repository import SqlRejectionRepository
from newsbot.api.deps import get_db_session
from newsbot.api.schemas import CouncilVoteOut, RejectionOut

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/rejections", response_model=list[RejectionOut])
async def list_rejections(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=100, le=500),
) -> list[RejectionOut]:
    repo = SqlRejectionRepository(session)
    rejections = await repo.list_recent(limit=limit)
    return [RejectionOut(**r.__dict__) for r in rejections]


@router.get("/council-votes", response_model=list[CouncilVoteOut])
async def list_council_votes(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    story_id: UUID,
) -> list[CouncilVoteOut]:
    repo = SqlCouncilVoteRepository(session)
    votes = await repo.list_for_story(story_id)
    return [CouncilVoteOut(**v.__dict__) for v in votes]
