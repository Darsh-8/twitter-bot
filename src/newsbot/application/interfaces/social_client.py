from dataclasses import dataclass
from typing import Protocol


class SocialPostError(Exception):
    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(slots=True)
class PostResult:
    success: bool
    x_tweet_id: str | None
    is_dry_run: bool
    raw_response: dict | None = None


class SocialPostClient(Protocol):
    async def post(self, text: str, image_url: str | None = None) -> PostResult: ...
