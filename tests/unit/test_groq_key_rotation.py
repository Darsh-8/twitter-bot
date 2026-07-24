import httpx
import openai
import pytest

from newsbot.adapters.llm.groq_provider import GroqLLMProvider
from newsbot.application.dto import StoryContext
from newsbot.application.interfaces.llm_provider import LLMProviderError


def _rate_limit_error() -> openai.APIStatusError:
    response = httpx.Response(status_code=429, request=httpx.Request("POST", "https://api.groq.com/x"))
    return openai.APIStatusError("rate limited", response=response, body=None)


class FakeCompletions:
    def __init__(self, behavior):
        self._behavior = behavior
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        result = self._behavior
        if isinstance(result, Exception):
            raise result
        return result


class FakeChat:
    def __init__(self, completions: FakeCompletions):
        self.completions = completions


class FakeClient:
    def __init__(self, behavior):
        self.completions = FakeCompletions(behavior)
        self.chat = FakeChat(self.completions)


def _fake_response(json_body: str):
    class Message:
        content = json_body

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    return Response()


def _story() -> StoryContext:
    return StoryContext(canonical_title="t", summary="s", source_count=1, source_names=["a"])


def _make_provider(behaviors: list) -> GroqLLMProvider:
    provider = GroqLLMProvider.__new__(GroqLLMProvider)
    provider._model = "test-model"
    provider._clients = [FakeClient(b) for b in behaviors]
    provider._cooldown_until = [0.0] * len(behaviors)
    provider._rotor = 0
    return provider


@pytest.mark.asyncio
async def test_first_key_success_is_used_directly():
    provider = _make_provider([_fake_response('{"approve": true, "reasoning": "ok"}')])
    result = await provider.council_vote(_story(), "persona")
    assert result.approve is True
    assert provider._clients[0].completions.calls == 1


@pytest.mark.asyncio
async def test_rate_limited_key_fails_over_to_next_key():
    behaviors = [_rate_limit_error(), _fake_response('{"approve": false, "reasoning": "no"}')]
    provider = _make_provider(behaviors)
    result = await provider.council_vote(_story(), "persona")
    assert result.approve is False
    assert provider._clients[0].completions.calls == 1
    assert provider._clients[1].completions.calls == 1
    assert provider._cooldown_until[0] > 0.0


@pytest.mark.asyncio
async def test_all_keys_rate_limited_raises_retryable_error():
    behaviors = [_rate_limit_error(), _rate_limit_error()]
    provider = _make_provider(behaviors)
    with pytest.raises(LLMProviderError) as exc_info:
        await provider.council_vote(_story(), "persona")
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_rotor_advances_so_load_spreads_across_keys():
    provider = _make_provider(
        [
            _fake_response('{"approve": true, "reasoning": "a"}'),
            _fake_response('{"approve": true, "reasoning": "b"}'),
        ]
    )
    await provider.council_vote(_story(), "persona")
    await provider.council_vote(_story(), "persona")
    assert provider._clients[0].completions.calls == 1
    assert provider._clients[1].completions.calls == 1
