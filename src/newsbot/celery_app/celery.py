from celery import Celery

from newsbot.config.settings import get_settings
from newsbot.logging_config import configure_logging

settings = get_settings()
configure_logging(settings)

celery_app = Celery(
    "newsbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "newsbot.celery_app.tasks.poll_sources_task",
        "newsbot.celery_app.tasks.process_pipeline_task",
        "newsbot.celery_app.tasks.post_tweet_task",
    ],
)

celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.timezone,
    enable_utc=True,
)

from newsbot.celery_app.beat_schedule import build_beat_schedule  # noqa: E402

celery_app.conf.beat_schedule = build_beat_schedule(settings)
