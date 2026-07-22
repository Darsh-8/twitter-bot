from typing import Protocol

from newsbot.domain.models import Article, Source


class SourceFetchError(Exception):
    def __init__(self, message: str, source_name: str) -> None:
        super().__init__(message)
        self.source_name = source_name


class NewsSourceClient(Protocol):
    async def fetch(self, source: Source) -> list[Article]: ...
