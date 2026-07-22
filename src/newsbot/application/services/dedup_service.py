from datetime import datetime, timedelta, timezone

import structlog

from newsbot.application.interfaces.repositories import ArticleRepository, StoryRepository
from newsbot.domain.models import Article, Story

logger = structlog.get_logger(__name__)

LOOKBACK_HOURS = 72


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class DedupService:
    def __init__(self, article_repo: ArticleRepository, story_repo: StoryRepository, similarity_threshold: float) -> None:
        self._article_repo = article_repo
        self._story_repo = story_repo
        self._similarity_threshold = similarity_threshold

    async def cluster_new_articles(self) -> dict:
        since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
        unclustered = await self._article_repo.list_unclustered(since)
        stats = {"attached_to_existing": 0, "merged_new_cluster": 0, "created_single": 0}
        pending: list[Article] = []

        for article in unclustered:
            if article.embedding is None:
                continue
            matches = await self._story_repo.find_similar(article.embedding, since, limit=1)
            if matches and matches[0][1] >= self._similarity_threshold:
                story, score = matches[0]
                await self._article_repo.attach_to_story(article.id, story.id)
                await self._story_repo.increment_source_count(story.id, score, article.id)
                stats["attached_to_existing"] += 1
                logger.info("article_attached_to_story", article_id=str(article.id), story_id=str(story.id), similarity=score)
                continue
            pending.append(article)

        used: set = set()
        for i, article in enumerate(pending):
            if article.id in used:
                continue
            cluster = [article]
            for other in pending[i + 1 :]:
                if other.id in used or other.embedding is None or article.embedding is None:
                    continue
                if _cosine_similarity(article.embedding, other.embedding) >= self._similarity_threshold:
                    cluster.append(other)
                    used.add(other.id)
            used.add(article.id)

            story = Story(
                id=None,
                canonical_title=cluster[0].title,
                summary=cluster[0].summary or cluster[0].title,
                embedding=cluster[0].embedding,
                source_count=len(cluster),
            )
            saved_story = await self._story_repo.add(story)
            for member in cluster:
                await self._article_repo.attach_to_story(member.id, saved_story.id)

            if len(cluster) > 1:
                stats["merged_new_cluster"] += 1
            else:
                stats["created_single"] += 1
            logger.info(
                "story_created",
                story_id=str(saved_story.id),
                title=saved_story.canonical_title,
                source_count=saved_story.source_count,
            )

        return stats
