import pytest
from pydantic import ValidationError

from djx.analyzer.schema import TweetAnalysis


def test_defaults_match_spec():
    a = TweetAnalysis()
    assert a.artists == []
    assert a.tracks == []
    assert a.is_new_release is False
    assert a.release_type is None
    assert a.streaming_links == []
    assert a.mood == "neutral"
    assert a.energy_level == "medium"
    assert a.recommended_artists == []
    assert a.hashtags == []
    assert 0.0 <= a.confidence <= 1.0


def test_rejects_bad_mood():
    with pytest.raises(ValidationError):
        TweetAnalysis(mood="weird")


def test_rejects_bad_release_type():
    with pytest.raises(ValidationError):
        TweetAnalysis(release_type="lp")


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        TweetAnalysis(confidence=1.5)
    with pytest.raises(ValidationError):
        TweetAnalysis(confidence=-0.1)


def test_dedup_strings():
    a = TweetAnalysis(artists=["a", "a", " a ", "b"])
    assert a.artists == ["a", "b"]


def test_round_trip_json():
    a = TweetAnalysis(
        artists=["x"],
        tracks=["t"],
        is_new_release=True,
        release_type="single",
        streaming_links=["https://open.spotify.com/track/1"],
        mood="hype",
        energy_level="high",
        recommended_artists=["y"],
        hashtags=["tag"],
        confidence=0.9,
    )
    j = a.model_dump_json()
    b = TweetAnalysis.model_validate_json(j)
    assert b == a
