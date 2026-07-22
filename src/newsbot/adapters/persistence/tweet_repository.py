from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.models_orm import TweetORM
from newsbot.domain.enums import TweetStatus
from newsbot.domain.models import PostedTweet


def _to_domain(row: TweetORM) -> PostedTweet:
    return PostedTweet(
        id=row.id,
        story_id=row.story_id,
        tweet_text=row.tweet_text,
        tweet_style=row.tweet_style,
        is_dry_run=row.is_dry_run,
        status=TweetStatus(row.status),
        x_tweet_id=row.x_tweet_id,
        posted_at=row.posted_at,
        failure_reason=row.failure_reason,
        retry_count=row.retry_count,
    )


class SqlTweetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tweet: PostedTweet) -> PostedTweet:
        row = TweetORM(
            story_id=tweet.story_id,
            tweet_text=tweet.tweet_text,
            tweet_style=tweet.tweet_style,
            is_dry_run=tweet.is_dry_run,
            status=tweet.status.value,
            x_tweet_id=tweet.x_tweet_id,
            posted_at=tweet.posted_at,
            failure_reason=tweet.failure_reason,
            retry_count=tweet.retry_count,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def count_since(self, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count(TweetORM.id)).where(
                TweetORM.created_at >= since,
                TweetORM.status.in_([TweetStatus.POSTED.value, TweetStatus.DRY_RUN_POSTED.value]),
            )
        )
        return result.scalar_one()

    async def last_posted_at(self) -> datetime | None:
        result = await self._session.execute(
            select(func.max(TweetORM.posted_at)).where(
                TweetORM.status.in_([TweetStatus.POSTED.value, TweetStatus.DRY_RUN_POSTED.value])
            )
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 50) -> list[PostedTweet]:
        result = await self._session.execute(
            select(TweetORM).order_by(TweetORM.created_at.desc()).limit(limit)
        )
        return [_to_domain(row) for row in result.scalars().all()]
