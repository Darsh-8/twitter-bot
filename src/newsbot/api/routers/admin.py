from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.api.deps import get_db_session
from newsbot.composition import build_orchestrator

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/trigger/poll")
async def trigger_poll(session: Annotated[AsyncSession, Depends(get_db_session)]) -> dict:
    orchestrator = build_orchestrator(session)
    stats = await orchestrator.run_poll_cycle()
    await session.commit()
    return stats


@router.post("/trigger/process")
async def trigger_process(session: Annotated[AsyncSession, Depends(get_db_session)]) -> dict:
    orchestrator = build_orchestrator(session)
    stats = await orchestrator.run_process_cycle()
    await session.commit()
    return stats


@router.post("/trigger/post")
async def trigger_post(session: Annotated[AsyncSession, Depends(get_db_session)]) -> dict:
    orchestrator = build_orchestrator(session)
    posted = await orchestrator.run_posting_window(max_stories=1)
    await session.commit()
    return {"posted": posted}
