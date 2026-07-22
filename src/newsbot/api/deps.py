from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.db import get_session_factory
from newsbot.application.services.pipeline_orchestrator import PipelineOrchestrator
from newsbot.composition import build_orchestrator


async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_orchestrator(session: AsyncSession) -> PipelineOrchestrator:
    return build_orchestrator(session)
