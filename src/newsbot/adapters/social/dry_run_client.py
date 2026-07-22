import structlog

from newsbot.application.interfaces.social_client import PostResult

logger = structlog.get_logger(__name__)


class DryRunXClient:
    async def post(self, text: str, image_url: str | None = None) -> PostResult:
        logger.info("dry_run_would_post", tweet_text=text, image_url=image_url)
        return PostResult(success=True, x_tweet_id=None, is_dry_run=True, raw_response=None)
