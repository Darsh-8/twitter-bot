import asyncio
from datetime import datetime, timezone

import structlog

from newsbot.adapters.persistence.db import dispose_engine, session_scope
from newsbot.adapters.persistence.models_orm import PipelineRunORM
from newsbot.application.interfaces.llm_provider import LLMProviderError
from newsbot.celery_app.celery import celery_app
from newsbot.composition import build_orchestrator

logger = structlog.get_logger(__name__)


async def _run() -> dict:
    async with session_scope() as session:
        run = PipelineRunORM(run_type="process", status="success")
        session.add(run)
        await session.flush()

        orchestrator = build_orchestrator(session)
        stats: dict | None = None
        try:
            stats = await orchestrator.run_process_cycle()
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
    name="newsbot.celery_app.tasks.process_pipeline_task.process_pipeline",
    bind=True,
    autoretry_for=(LLMProviderError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def process_pipeline(self) -> dict:
    async def _wrapped() -> dict:
        try:
            return await _run()
        finally:
            await dispose_engine()

    return asyncio.run(_wrapped())
