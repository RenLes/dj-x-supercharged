from djx.analyzer.schema import TweetAnalysis
from djx.insights.virality import detect_viral_artists


def test_artists_above_threshold_surface():
    analyses = [
        TweetAnalysis(artists=["Kendrick"]),
        TweetAnalysis(artists=["Kendrick"]),
        TweetAnalysis(artists=["Kendrick"]),
        TweetAnalysis(artists=["Drake"]),
    ]
    out = detect_viral_artists(analyses, min_mentions=2)
    names = [n for n, _ in out]
    assert "Kendrick" in names
    assert "Drake" not in names


def test_release_mention_boost():
    analyses = [
        TweetAnalysis(artists=["A"], is_new_release=True),
        TweetAnalysis(artists=["B"]),
        TweetAnalysis(artists=["B"]),
        TweetAnalysis(artists=["B"]),
    ]
    out = detect_viral_artists(analyses, min_mentions=2)
    d = dict(out)
    assert d["A"] == 1 + 2  # 1 mention + release bonus
    assert d["B"] == 3


def test_recommended_artists_count():
    analyses = [
        TweetAnalysis(recommended_artists=["X"]),
        TweetAnalysis(recommended_artists=["X"]),
    ]
    out = detect_viral_artists(analyses, min_mentions=2)
    assert dict(out).get("X") == 2


def test_empty():
    assert detect_viral_artists([], min_mentions=1) == []
