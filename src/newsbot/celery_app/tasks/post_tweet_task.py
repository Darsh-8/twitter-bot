import asyncio
from datetime import datetime, timezone

import structlog

from newsbot.adapters.persistence.db import dispose_engine, session_scope
from newsbot.adapters.persistence.models_orm import PipelineRunORM
from newsbot.application.interfaces.social_client import SocialPostError
from newsbot.celery_app.celery import celery_app
from newsbot.composition import build_orchestrator

logger = structlog.get_logger(__name__)


async def _run() -> int:
    async with session_scope() as session:
        run = PipelineRunORM(run_type="post", status="success")
        session.add(run)
        await session.flush()

        orchestrator = build_orchestrator(session)
        posted = 0
        try:
            posted = await orchestrator.run_posting_window(max_stories=1)
            run.status = "success"
        except Exception:
            run.status = "failure"
            raise
        finally:
            run.finished_at = datetime.now(timezone.utc)
            run.stats = {"posted": posted}
    return posted


@celery_app.task(
    name="newsbot.celery_app.tasks.post_tweet_task.run_posting_window",
    bind=True,
    autoretry_for=(SocialPostError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def run_posting_window(self) -> int:
    async def _wrapped() -> int:
        try:
            return await _run()
        finally:
            await dispose_engine()

    return asyncio.run(_wrapped())
