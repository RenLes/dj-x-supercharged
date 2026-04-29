from djx.analyzer.heuristic import HeuristicAnalyzer

A = HeuristicAnalyzer()


def test_detects_spotify_link_as_release():
    res = A.analyze_sync("New single is OUT NOW: https://open.spotify.com/track/abc123 #vibes")
    assert res.is_new_release is True
    assert res.release_type == "single"
    assert any("open.spotify.com" in u for u in res.streaming_links)
    assert "vibes" in res.hashtags
    assert res.confidence >= 0.7


def test_album_keyword():
    res = A.analyze_sync("My new album drops Friday — pre-save now")
    assert res.is_new_release is True
    assert res.release_type == "album"


def test_quoted_track_title():
    res = A.analyze_sync('Working on "Midnight Drive" with @somebody')
    assert "Midnight Drive" in res.tracks
    assert "somebody" in res.artists


def test_neutral_when_no_signals():
    res = A.analyze_sync("good morning everyone")
    assert res.is_new_release is False
    assert res.release_type is None
    assert res.streaming_links == []
    assert res.mood == "neutral"


def test_mood_hype():
    res = A.analyze_sync("This song is FIRE 🔥 absolute banger")
    assert res.mood == "hype"
    assert res.energy_level == "high"


def test_mood_chill():
    res = A.analyze_sync("Sunday morning, smooth lo-fi vibes")
    assert res.mood == "chill"
    assert res.energy_level == "low"


def test_dedup_artists():
    res = A.analyze_sync("@same and @same again @other")
    assert res.artists == ["same", "other"]


def test_non_streaming_link_does_not_force_release():
    res = A.analyze_sync("read this: https://example.com/blog")
    assert res.is_new_release is False
    assert res.streaming_links == []
