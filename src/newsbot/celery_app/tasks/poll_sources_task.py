import asyncio
from datetime import datetime, timezone

import structlog

from newsbot.adapters.persistence.db import dispose_engine, session_scope
from newsbot.adapters.persistence.models_orm import PipelineRunORM
from newsbot.application.interfaces.source_client import SourceFetchError
from newsbot.celery_app.celery import celery_app
from newsbot.composition import build_orchestrator

logger = structlog.get_logger(__name__)


async def _run() -> dict:
    async with session_scope() as session:
        run = PipelineRunORM(run_type="poll", status="success")
        session.add(run)
        await session.flush()

        orchestrator = build_orchestrator(session)
        stats: dict | None = None
        try:
            stats = await orchestrator.run_poll_cycle()
            run.status = "success"
        except Exception:
            run.status = "failure"
            raise
        finally:
            run.finished_at = datetime.now(timezone.utc)
            run.stats = stats
            await orchestrator.aclose()
    return stats or {}


@celery_app.task(
    name="newsbot.celery_app.tasks.poll_sources_task.poll_sources",
    bind=True,
    autoretry_for=(SourceFetchError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def poll_sources(self) -> dict:
    async def _wrapped() -> dict:
        try:
            return await _run()
        finally:
            await dispose_engine()

    return asyncio.run(_wrapped())
