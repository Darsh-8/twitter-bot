"""Run the story council against a story without posting or touching the gate/frequency
limits. Useful for tuning council personas/threshold before wiring into real posting.

Note: council votes ARE persisted to the council_votes table (same code path as a real
review), since that's the whole point of previewing -- only actual posting is skipped.

Usage: python scripts/preview_council.py [--story-id UUID]
Without --story-id, previews the oldest story currently in 'approved' status.
"""

import argparse
import asyncio
import sys
from uuid import UUID

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from newsbot.adapters.llm.base import COUNCIL_PERSONAS
from newsbot.adapters.llm.factory import get_llm_provider
from newsbot.adapters.persistence.article_repository import SqlArticleRepository
from newsbot.adapters.persistence.council_vote_repository import SqlCouncilVoteRepository
from newsbot.adapters.persistence.db import session_scope
from newsbot.adapters.persistence.source_repository import SqlSourceRepository
from newsbot.adapters.persistence.story_repository import SqlStoryRepository
from newsbot.application.services.story_council_service import StoryCouncilService
from newsbot.config.settings import get_settings
from newsbot.domain.enums import StoryStatus
from newsbot.logging_config import configure_logging


async def main(story_id: UUID | None) -> None:
    settings = get_settings()
    configure_logging(settings)

    async with session_scope() as session:
        story_repo = SqlStoryRepository(session)
        article_repo = SqlArticleRepository(session)
        source_repo = SqlSourceRepository(session)
        council_vote_repo = SqlCouncilVoteRepository(session)

        if story_id is not None:
            story = await story_repo.get(story_id)
            if story is None:
                print(f"No story found with id {story_id}")
                return
        else:
            approved = await story_repo.list_by_status(StoryStatus.APPROVED, limit=1)
            if not approved:
                print("No stories currently in 'approved' status. Run the process cycle first.")
                return
            story = approved[0]

        articles = await article_repo.list_by_story(story.id)
        source_names = []
        for article in articles:
            source = await source_repo.get_by_id(article.source_id)
            source_names.append(source.name if source else "unknown")

        llm = get_llm_provider(settings)
        council_service = StoryCouncilService(
            llm,
            council_vote_repo,
            COUNCIL_PERSONAS,
            settings.council_approval_threshold,
            settings.llm_call_delay_seconds,
        )
        verdict = await council_service.review(story, source_names)

    print(f"\nStory: {story.canonical_title}")
    print(f"Confidence: {story.confidence_score:.2f} | Importance: {story.importance_score:.2f} | Category: {story.category}")
    print()
    for vote in verdict.votes:
        mark = "APPROVE" if vote.approve else "REJECT "
        print(f"[{mark}] {vote.persona_name}: {vote.reasoning}")
    approve_count = sum(1 for v in verdict.votes if v.approve)
    print(f"\n{approve_count}/{len(verdict.votes)} approved (threshold={settings.council_approval_threshold})")
    print(f"Final verdict: {'PASSES council' if verdict.approved else 'REJECTED by council'}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--story-id", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(main(UUID(args.story_id) if args.story_id else None))
