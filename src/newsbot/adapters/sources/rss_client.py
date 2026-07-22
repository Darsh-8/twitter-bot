import asyncio
import html
from datetime import datetime, timezone

import feedparser
import httpx

from newsbot.application.interfaces.source_client import SourceFetchError
from newsbot.domain.models import Article, Source


def _parse_datetime(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        value = getattr(entry, field, None)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)
    return None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    # feedparser doesn't always decode HTML entities (e.g. &#8217;) depending on
    # the feed's declared content type, so unescape defensively as a safety net.
    return html.unescape(value).strip() or None


DEFAULT_USER_AGENT = "AINewsBot/1.0 (RSS reader; https://github.com/; contact: admin@example.com)"


class RSSSourceClient:
    def __init__(self, timeout_seconds: float = 15.0, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent

    async def fetch(self, source: Source) -> list[Article]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, headers={"User-Agent": self._user_agent}
            ) as client:
                response = await client.get(source.url, follow_redirects=True)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            detail = str(exc) or exc.__class__.__name__
            raise SourceFetchError(f"Failed to fetch RSS feed: {detail}", source_name=source.name) from exc

        parsed = await asyncio.to_thread(feedparser.parse, response.content)
        if parsed.bozo and not parsed.entries:
            raise SourceFetchError(
                f"Failed to parse RSS feed: {parsed.bozo_exception}", source_name=source.name
            )

        articles: list[Article] = []
        for entry in parsed.entries:
            external_id = getattr(entry, "id", None) or getattr(entry, "link", None)
            if not external_id:
                continue
            articles.append(
                Article(
                    id=None,
                    source_id=source.id,
                    external_id=external_id,
                    title=_clean_text(getattr(entry, "title", "")) or "",
                    url=getattr(entry, "link", ""),
                    summary=_clean_text(getattr(entry, "summary", None)),
                    content=None,
                    published_at=_parse_datetime(entry),
                    raw_payload={"title": getattr(entry, "title", ""), "link": getattr(entry, "link", "")},
                )
            )
        return articles
