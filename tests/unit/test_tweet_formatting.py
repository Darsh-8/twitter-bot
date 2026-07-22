from newsbot.application.services.tweet_generation_service import (
    MAX_TWEET_LENGTH,
    STYLE_HINTS,
    enforce_tweet_length,
    next_style_hint,
)


def test_short_tweet_is_unchanged():
    text = "OpenAI just shipped something interesting."
    assert enforce_tweet_length(text) == text


def test_long_tweet_is_truncated_to_max_length():
    text = "a" * 400
    result = enforce_tweet_length(text)
    assert len(result) <= MAX_TWEET_LENGTH


def test_truncation_breaks_on_word_boundary_and_adds_ellipsis():
    text = "word " * 100
    result = enforce_tweet_length(text)
    assert result.endswith("…")
    assert not result[:-1].endswith(" ")


def test_style_hint_rotates_through_all_styles():
    seen = {next_style_hint() for _ in range(len(STYLE_HINTS) * 2)}
    assert seen == set(STYLE_HINTS)
