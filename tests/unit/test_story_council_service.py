from uuid import uuid4

import pytest

from newsbot.application.dto import CouncilVoteResult
from newsbot.application.interfaces.llm_provider import LLMProviderError
from newsbot.application.services.story_council_service import StoryCouncilService
from newsbot.domain.enums import StoryStatus
from newsbot.domain.models import Story


class FakeCouncilVoteRepository:
    def __init__(self):
        self.votes = []

    async def add(self, vote):
        self.votes.append(vote)
        return vote

    async def list_for_story(self, story_id):
        return [v for v in self.votes if v.story_id == story_id]


class ScriptedLLM:
    """Returns one canned CouncilVoteResult per call, in order, keyed by persona name."""

    def __init__(self, results_by_persona: dict):
        self._results_by_persona = results_by_persona

    async def council_vote(self, story, persona_prompt):
        for name, result in self._results_by_persona.items():
            if name in persona_prompt:
                return result
        raise AssertionError(f"No scripted result for persona prompt: {persona_prompt}")


class FailingPersonaLLM:
    async def council_vote(self, story, persona_prompt):
        raise LLMProviderError("boom", retryable=True)


def _story():
    return Story(id=uuid4(), canonical_title="Title", summary="Summary", status=StoryStatus.APPROVED)


PERSONAS = [
    ("Persona A", "Persona A prompt"),
    ("Persona B", "Persona B prompt"),
    ("Persona C", "Persona C prompt"),
]


@pytest.mark.asyncio
async def test_majority_approve_passes():
    llm = ScriptedLLM(
        {
            "Persona A prompt": CouncilVoteResult(approve=True, reasoning="good"),
            "Persona B prompt": CouncilVoteResult(approve=True, reasoning="good"),
            "Persona C prompt": CouncilVoteResult(approve=False, reasoning="meh"),
        }
    )
    repo = FakeCouncilVoteRepository()
    service = StoryCouncilService(
        llm=llm,
        council_vote_repo=repo,
        personas=PERSONAS,
        approval_threshold=0.6,
        llm_call_delay_seconds=0,
    )
    verdict = await service.review(_story(), source_names=["Source A"])
    assert verdict.approved is True
    assert len(verdict.votes) == 3
    assert len(repo.votes) == 3


@pytest.mark.asyncio
async def test_majority_reject_fails():
    llm = ScriptedLLM(
        {
            "Persona A prompt": CouncilVoteResult(approve=False, reasoning="meh"),
            "Persona B prompt": CouncilVoteResult(approve=False, reasoning="meh"),
            "Persona C prompt": CouncilVoteResult(approve=True, reasoning="good"),
        }
    )
    repo = FakeCouncilVoteRepository()
    service = StoryCouncilService(
        llm=llm,
        council_vote_repo=repo,
        personas=PERSONAS,
        approval_threshold=0.6,
        llm_call_delay_seconds=0,
    )
    verdict = await service.review(_story(), source_names=["Source A"])
    assert verdict.approved is False


@pytest.mark.asyncio
async def test_all_personas_failing_fails_closed():
    repo = FakeCouncilVoteRepository()
    service = StoryCouncilService(
        llm=FailingPersonaLLM(),
        council_vote_repo=repo,
        personas=PERSONAS,
        approval_threshold=0.6,
        llm_call_delay_seconds=0,
    )
    verdict = await service.review(_story(), source_names=["Source A"])
    assert verdict.approved is False
    assert verdict.votes == []
    assert repo.votes == []
