import asyncio

from djx.podcasts.signals import _heuristic_signal, extract_podcast_signals


def test_heuristic_detects_known_host():
    s = _heuristic_signal("Joe Rogan absolutely cooked his guest yesterday")
    assert s.host == "Joe Rogan"
    assert s.show == "The Joe Rogan Experience"
    assert "comedy" in s.topics or "long-form" in s.topics


def test_heuristic_detects_show_alias():
    s = _heuristic_signal("This JRE episode was wild")
    assert s.host == "Joe Rogan"


def test_heuristic_extracts_guest_with_x_pattern():
    s = _heuristic_signal("Lex Fridman with Elon Musk - 4 hour deep dive")
    assert s.host == "Lex Fridman"
    assert s.guest == "Elon Musk"


def test_heuristic_marks_clip_with_spotify_link():
    s = _heuristic_signal(
        "Best part: https://open.spotify.com/episode/abc123 #podcast"
    )
    assert s.is_podcast_clip is True
    assert any("spotify.com" in u for u in s.streaming_links)
    assert s.confidence >= 0.5


def test_heuristic_no_signal_for_random_tweet():
    s = _heuristic_signal("good morning everyone, beautiful sunny day")
    assert s.is_podcast_clip is False
    assert s.host is None
    assert s.confidence < 0.3


def test_heuristic_topic_hint_from_quoted_text():
    s = _heuristic_signal(
        'Andrew Huberman explains "the dopamine reset protocol" in this clip'
    )
    assert s.host == "Andrew Huberman"
    assert s.topic_hint == "the dopamine reset protocol"


def test_heuristic_clip_keywords():
    s = _heuristic_signal("This podcast clip is fire — the moment at 1:23:45")
    assert s.is_podcast_clip is True
    assert "clip" in s.clip_keywords


def test_async_wrapper_returns_signal():
    out = asyncio.run(extract_podcast_signals("Joe Rogan and Theo Von podcast"))
    assert out.host == "Joe Rogan"


def test_no_llm_no_escalation_when_high_confidence():
    # If a clip already has high confidence, the enricher should not be called.
    called = []

    async def fake_enricher(text, base):
        called.append(text)
        return base

    out = asyncio.run(extract_podcast_signals(
        "https://open.spotify.com/episode/abc Joe Rogan with Elon Musk new ep",
        llm_enricher=fake_enricher,
    ))
    assert out.is_podcast_clip is True
    assert called == []  # high confidence → no escalation
