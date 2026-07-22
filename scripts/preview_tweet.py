"""Preview the tweet the LLM would generate for an approved story, without posting or
touching the posting gate/frequency limits. Useful for iterating on the tweet-generation
prompt without waiting out MIN_POST_INTERVAL_MINUTES between real runs.

Usage: python scripts/preview_tweet.py [--story-id UUID]
Without --story-id, previews the oldest story currently in 'approved' status.
"""

import argparse
import asyncio
import sys
from uuid import UUID

# Windows terminals often default to a non-UTF-8 codepage, which mangles curly
# quotes/em-dashes/accented characters in generated tweets into "?" or "�".
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from newsbot.adapters.llm.factory import get_llm_provider
from newsbot.adapters.persistence.article_repository import SqlArticleRepository
from newsbot.adapters.persistence.db import session_scope
from newsbot.adapters.persistence.source_repository import SqlSourceRepository
from newsbot.adapters.persistence.story_repository import SqlStoryRepository
from newsbot.application.services.tweet_generation_service import TweetGenerationService
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
        tweet_service = TweetGenerationService(llm)
        draft = await tweet_service.generate(story, source_names)

    print(f"\nStory: {story.canonical_title}")
    print(f"Confidence: {story.confidence_score:.2f} | Importance: {story.importance_score:.2f}")
    print(f"Style: {draft.style}")
    print(f"Thread recommended: {draft.thread_recommended}")
    print(f"\nTweet ({len(draft.text)} chars):\n{draft.text}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--story-id", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(main(UUID(args.story_id) if args.story_id else None))
