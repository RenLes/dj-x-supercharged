from djx.analyzer.schema import TweetAnalysis
from djx.recommender.seeds import build_seeds


def test_top_artist_gets_base_weight():
    pool = build_seeds([{"name": "Artist A"}], {}, [])
    assert pool.artist_weights["Artist A"] == 5


def test_release_tweet_bumps_artist():
    a = TweetAnalysis(is_new_release=True, mood="hype", energy_level="high")
    pool = build_seeds([{"name": "Artist A"}], {"Artist A": [a]}, [])
    assert pool.artist_weights["Artist A"] >= 5 + 5


def test_user_likes_promote_mentioned_artists():
    a = TweetAnalysis(artists=["Friend"], recommended_artists=["Discover"])
    pool = build_seeds([{"name": "Top"}], {}, [a])
    assert pool.artist_weights["Friend"] >= 3
    assert pool.artist_weights["Discover"] >= 2


def test_streaming_links_aggregate():
    a = TweetAnalysis(streaming_links=["https://open.spotify.com/track/1"])
    pool = build_seeds([], {"X": [a]}, [])
    assert "https://open.spotify.com/track/1" in pool.streaming_links
