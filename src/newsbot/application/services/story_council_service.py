import asyncio
from dataclasses import dataclass, field
from uuid import UUID

import structlog

from newsbot.application.dto import StoryContext
from newsbot.application.interfaces.llm_provider import LLMProvider, LLMProviderError
from newsbot.application.interfaces.repositories import CouncilVoteRepository
from newsbot.domain.models import CouncilVoteRecord, Story

logger = structlog.get_logger(__name__)

DEFAULT_COUNCIL_APPROVAL_THRESHOLD = 0.6
DEFAULT_LLM_CALL_DELAY_SECONDS = 3.0


@dataclass(slots=True)
class CouncilVote:
    persona_name: str
    approve: bool
    reasoning: str


@dataclass(slots=True)
class CouncilVerdict:
    approved: bool
    votes: list[CouncilVote] = field(default_factory=list)


class StoryCouncilService:
    def __init__(
        self,
        llm: LLMProvider,
        council_vote_repo: CouncilVoteRepository,
        personas: list[tuple[str, str]],
        approval_threshold: float = DEFAULT_COUNCIL_APPROVAL_THRESHOLD,
        llm_call_delay_seconds: float = DEFAULT_LLM_CALL_DELAY_SECONDS,
    ) -> None:
        self._llm = llm
        self._council_vote_repo = council_vote_repo
        self._personas = personas
        self._approval_threshold = approval_threshold
        self._llm_call_delay_seconds = llm_call_delay_seconds

    async def review(self, story: Story, source_names: list[str]) -> CouncilVerdict:
        assert story.id is not None
        story_id: UUID = story.id
        context = StoryContext(
            canonical_title=story.canonical_title,
            summary=story.summary,
            source_count=story.source_count,
            source_names=source_names,
            category_hint=story.category,
        )

        votes: list[CouncilVote] = []
        for persona_name, persona_prompt in self._personas:
            try:
                result = await self._llm.council_vote(context, persona_prompt)
            except LLMProviderError as exc:
                logger.warning(
                    "council_vote_llm_error",
                    story_id=str(story_id),
                    persona=persona_name,
                    error=str(exc),
                    retryable=exc.retryable,
                )
                # Treat a failed vote call as an abstention (does not count toward
                # approval) rather than crashing the whole council review.
                continue
            finally:
                await asyncio.sleep(self._llm_call_delay_seconds)

            vote = CouncilVote(persona_name=persona_name, approve=result.approve, reasoning=result.reasoning)
            votes.append(vote)
            await self._council_vote_repo.add(
                CouncilVoteRecord(
                    story_id=story_id,
                    persona_name=persona_name,
                    approve=result.approve,
                    reasoning=result.reasoning,
                )
            )
            logger.info(
                "council_vote_cast",
                story_id=str(story_id),
                persona=persona_name,
                approve=result.approve,
                reasoning=result.reasoning,
            )

        if not votes:
            # Every persona failed to respond -- fail closed rather than post on no data.
            return CouncilVerdict(approved=False, votes=votes)

        approve_count = sum(1 for v in votes if v.approve)
        approved = (approve_count / len(votes)) >= self._approval_threshold
        logger.info(
            "council_verdict",
            story_id=str(story_id),
            approve_count=approve_count,
            total_votes=len(votes),
            approved=approved,
        )
        return CouncilVerdict(approved=approved, votes=votes)
