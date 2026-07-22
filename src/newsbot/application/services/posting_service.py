from datetime import datetime, timezone
from uuid import UUID

import structlog

from newsbot.application.interfaces.repositories import TweetRepository
from newsbot.application.interfaces.social_client import SocialPostClient, SocialPostError
from newsbot.domain.enums import TweetStatus
from newsbot.domain.models import PostedTweet, TweetDraft

logger = structlog.get_logger(__name__)


class PostingService:
    def __init__(self, tweet_repo: TweetRepository, social_client: SocialPostClient) -> None:
        self._tweet_repo = tweet_repo
        self._social_client = social_client

    async def post(self, story_id: UUID, draft: TweetDraft) -> PostedTweet:
        try:
            result = await self._social_client.post(draft.text, image_url=draft.image_url)
        except SocialPostError as exc:
            tweet = PostedTweet(
                id=None,
                story_id=story_id,
                tweet_text=draft.text,
                tweet_style=draft.style,
                is_dry_run=False,
                status=TweetStatus.FAILED,
                failure_reason=str(exc),
            )
            saved = await self._tweet_repo.add(tweet)
            logger.error("tweet_post_failed", story_id=str(story_id), error=str(exc), retryable=exc.retryable)
            if exc.retryable:
                raise
            return saved

        status = TweetStatus.DRY_RUN_POSTED if result.is_dry_run else TweetStatus.POSTED
        tweet = PostedTweet(
            id=None,
            story_id=story_id,
            tweet_text=draft.text,
            tweet_style=draft.style,
            is_dry_run=result.is_dry_run,
            status=status,
            x_tweet_id=result.x_tweet_id,
            posted_at=datetime.now(timezone.utc),
        )
        saved = await self._tweet_repo.add(tweet)
        logger.info(
            "tweet_posted",
            story_id=str(story_id),
            is_dry_run=result.is_dry_run,
            x_tweet_id=result.x_tweet_id,
        )
        return saved
