from uuid import uuid4

import httpx
import pytest
import respx

from newsbot.adapters.sources.rss_client import RSSSourceClient
from newsbot.application.interfaces.source_client import SourceFetchError
from newsbot.domain.models import Source

FEED_URL = "https://broken.example.com/feed.xml"


def _source() -> Source:
    return Source(id=uuid4(), name="Broken Feed", source_type="rss", url=FEED_URL, category="tech_media")


@pytest.mark.asyncio
@respx.mock
async def test_http_error_raises_source_fetch_error():
    respx.get(FEED_URL).mock(return_value=httpx.Response(503))
    client = RSSSourceClient()
    with pytest.raises(SourceFetchError):
        await client.fetch(_source())


@pytest.mark.asyncio
@respx.mock
async def test_entries_without_link_are_skipped():
    xml = b"""<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>No link here</title></item>
    </channel></rss>"""
    respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=xml))
    client = RSSSourceClient()
    articles = await client.fetch(_source())
    assert articles == []
