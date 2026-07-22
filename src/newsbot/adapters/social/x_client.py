import tweepy

from newsbot.application.interfaces.social_client import PostResult, SocialPostError


class TweepyXClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
    ) -> None:
        self._client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

    async def post(self, text: str, image_url: str | None = None) -> PostResult:
        try:
            response = self._client.create_tweet(text=text)
        except tweepy.TooManyRequests as exc:
            raise SocialPostError("X API rate limit exceeded", retryable=True) from exc
        except tweepy.TwitterServerError as exc:
            raise SocialPostError("X API server error", retryable=True) from exc
        except tweepy.Unauthorized as exc:
            raise SocialPostError("X API authentication failed", retryable=False) from exc
        except tweepy.BadRequest as exc:
            raise SocialPostError(f"X API rejected request: {exc}", retryable=False) from exc
        except tweepy.TweepyException as exc:
            raise SocialPostError(str(exc), retryable=False) from exc

        tweet_id = str(response.data["id"]) if response.data else None
        return PostResult(success=True, x_tweet_id=tweet_id, is_dry_run=False, raw_response=response.data)
