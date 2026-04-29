from djx.insights.trends import _post_count_to_int, summarize_trends


def test_post_count_parser():
    assert _post_count_to_int("1.2K posts") == 1200
    assert _post_count_to_int("186K posts") == 186_000
    assert _post_count_to_int("2.3M posts") == 2_300_000
    assert _post_count_to_int("500 posts") == 500
    assert _post_count_to_int(None) == 0
    assert _post_count_to_int("garbage") == 0


def test_summarize_picks_music_trends():
    trends = [
        {"trend_name": "New album drops Friday", "category": "Music", "post_count": "100K posts"},
        {"trend_name": "World Cup final", "category": "Sports", "post_count": "1.2M posts"},
        {"trend_name": "Some politician", "category": "News", "post_count": "5K posts"},
    ]
    out = summarize_trends(trends)
    assert any("album" in t["trend_name"].lower() for t in out.music_related)
    assert len(out.music_related) >= 1
    assert out.raw_count == 3


def test_summarize_event_signals():
    trends = [
        {"trend_name": "World Cup final tonight", "category": "Sports", "post_count": "1M posts"},
        {"trend_name": "Random thing", "category": "Misc", "post_count": "50 posts"},
    ]
    out = summarize_trends(trends)
    assert len(out.event_signals) >= 1


def test_summarize_sorts_by_count():
    trends = [
        {"trend_name": "small song", "category": "Music", "post_count": "100 posts"},
        {"trend_name": "huge album", "category": "Music", "post_count": "5M posts"},
    ]
    out = summarize_trends(trends)
    assert out.music_related[0]["trend_name"] == "huge album"
