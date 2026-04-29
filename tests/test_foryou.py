from djx.podcasts.foryou import topics_from_personalized_trends


def test_politics_keyword_in_trend_name():
    trends = [
        {"trend_name": "Zeldin Clashes with DeLauro Over EPA Budget and Climate Rules",
         "category": "News", "post_count": "186K posts"},
    ]
    topics = topics_from_personalized_trends(trends)
    assert "climate policy" in topics or "politics" in topics


def test_sports_category_yields_sports_topics():
    trends = [
        {"trend_name": "Random sports team", "category": "Sports", "post_count": "10K posts"},
    ]
    topics = topics_from_personalized_trends(trends)
    assert "sports" in topics or "sports analysis" in topics


def test_post_count_drives_ranking():
    trends = [
        {"trend_name": "Crypto news small", "category": "Other", "post_count": "100 posts"},
        {"trend_name": "AI news huge", "category": "Other", "post_count": "5M posts"},
    ]
    topics = topics_from_personalized_trends(trends)
    # The high-volume AI trend should beat the low-volume crypto trend
    if "ai" in topics and "crypto" in topics:
        assert topics.index("ai") < topics.index("crypto")
    else:
        assert "ai" in topics


def test_dedupe_topics():
    trends = [
        {"trend_name": "AI thing 1", "category": "Technology", "post_count": "1K posts"},
        {"trend_name": "AI thing 2", "category": "Technology", "post_count": "2K posts"},
    ]
    topics = topics_from_personalized_trends(trends)
    assert topics.count("ai") == 1


def test_empty_trends():
    assert topics_from_personalized_trends([]) == []


def test_max_topics_cap():
    trends = [
        {"trend_name": f"news {i}", "category": "News", "post_count": "1K posts"}
        for i in range(20)
    ]
    topics = topics_from_personalized_trends(trends, max_topics=5)
    assert len(topics) <= 5


def test_chubby_cat_doesnt_match_anything_specific():
    """Sanity check: bizarre trend names without keyword hits don't pollute output."""
    trends = [
        {"trend_name": "Chubby Cat Chrome Extension Blocks Endless Scrolling",
         "category": "News", "post_count": "1.2K posts"},
    ]
    topics = topics_from_personalized_trends(trends)
    # Should fall back to category mapping ("News" → news/current events/politics)
    # NOT crypto, ai, sports, etc.
    for bad in ["crypto", "sports", "fitness", "true crime"]:
        assert bad not in topics
