from newsbot.config.settings import Settings


def build_beat_schedule(settings: Settings) -> dict:
    return {
        "poll-sources": {
            "task": "newsbot.celery_app.tasks.poll_sources_task.poll_sources",
            "schedule": settings.poll_interval_minutes * 60.0,
        },
        "process-pipeline": {
            "task": "newsbot.celery_app.tasks.process_pipeline_task.process_pipeline",
            "schedule": settings.poll_interval_minutes * 60.0,
        },
        "posting-window": {
            "task": "newsbot.celery_app.tasks.post_tweet_task.run_posting_window",
            "schedule": settings.min_post_interval_minutes * 60.0,
        },
    }
