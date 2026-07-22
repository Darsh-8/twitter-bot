"""Run one full poll -> process -> post cycle locally for smoke testing.

Usage: python scripts/run_manual_cycle.py
Requires DATABASE_URL/REDIS_URL reachable and an LLM API key configured; defaults
to DRY_RUN=true so no real tweet is posted.

Each stage (poll/process/post) commits in its own DB transaction, mirroring how the
real Celery tasks are separated in production -- so a failure partway through one
stage (e.g. an LLM rate limit) doesn't roll back an earlier stage's already-committed
work.
"""

import argparse
import asyncio

from newsbot.adapters.persistence.db import session_scope
from newsbot.composition import build_orchestrator
from newsbot.config.settings import get_settings
from newsbot.logging_config import configure_logging


async def main(max_stories: int) -> None:
    settings = get_settings()
    configure_logging(settings)

    async with session_scope() as session:
        orchestrator = build_orchestrator(session)
        poll_stats = await orchestrator.run_poll_cycle()
    print("poll:", poll_stats)

    async with session_scope() as session:
        orchestrator = build_orchestrator(session)
        process_stats = await orchestrator.run_process_cycle()
    print("process:", process_stats)

    async with session_scope() as session:
        orchestrator = build_orchestrator(session)
        posted = await orchestrator.run_posting_window(max_stories=max_stories)
    print("posted:", posted)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-stories", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(main(args.max_stories))
