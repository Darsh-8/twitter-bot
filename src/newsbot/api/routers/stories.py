from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.adapters.persistence.story_repository import SqlStoryRepository
from newsbot.adapters.persistence.tweet_repository import SqlTweetRepository
from newsbot.api.deps import get_db_session
from newsbot.api.schemas import StoryOut, TweetOut
from newsbot.domain.enums import StoryStatus

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("", response_model=list[StoryOut])
async def list_stories(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status: StoryStatus | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> list[StoryOut]:
    repo = SqlStoryRepository(session)
    if status is not None:
        stories = await repo.list_by_status(status, limit=limit)
    else:
        stories = []
        for s in StoryStatus:
            stories.extend(await repo.list_by_status(s, limit=limit))
    return [StoryOut(**s.__dict__) for s in stories]


@router.get("/tweets", response_model=list[TweetOut])
async def list_tweets(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, le=200),
) -> list[TweetOut]:
    repo = SqlTweetRepository(session)
    tweets = await repo.list_recent(limit=limit)
    return [TweetOut(**t.__dict__) for t in tweets]
