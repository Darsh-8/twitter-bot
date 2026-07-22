from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from newsbot.application.interfaces.repositories import TweetRepository


@dataclass(slots=True)
class GateDecision:
    allowed: bool
    reason: str | None = None


class GatingService:
    def __init__(
        self,
        tweet_repo: TweetRepository,
        max_tweets_per_day: int,
        min_post_interval_minutes: int,
        min_breaking_interval_minutes: int,
    ) -> None:
        self._tweet_repo = tweet_repo
        self._max_tweets_per_day = max_tweets_per_day
        self._min_post_interval_minutes = min_post_interval_minutes
        self._min_breaking_interval_minutes = min_breaking_interval_minutes

    async def check(self, is_breaking: bool) -> GateDecision:
        now = datetime.now(timezone.utc)

        # Breaking news bypasses the daily cap entirely -- the importance rubric
        # already sets a high bar for is_breaking=true (frontier launches, landmark
        # rulings, major leadership shakeups), so it stays rare enough not to need
        # its own ceiling. Only the (shorter) interval gate below still applies.
        if not is_breaking:
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            posted_today = await self._tweet_repo.count_since(day_start)
            if posted_today >= self._max_tweets_per_day:
                return GateDecision(allowed=False, reason="daily_cap_reached")

        last_posted = await self._tweet_repo.last_posted_at()
        if last_posted is not None:
            min_interval = (
                self._min_breaking_interval_minutes if is_breaking else self._min_post_interval_minutes
            )
            elapsed = now - last_posted
            if elapsed < timedelta(minutes=min_interval):
                return GateDecision(allowed=False, reason="min_interval_not_met")

        return GateDecision(allowed=True)
