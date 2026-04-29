from djx.podcasts.resolver import _build_query, _strength
from djx.podcasts.signals import PodcastSignal


def test_build_query_combines_show_host_guest():
    s = PodcastSignal(
        host="Joe Rogan",
        show="The Joe Rogan Experience",
        guest="Elon Musk",
        topic_hint="Mars colony",
        is_podcast_clip=True,
        confidence=0.6,
    )
    q = _build_query(s)
    assert q is not None
    assert "Joe Rogan" in q
    assert "Elon Musk" in q


def test_build_query_returns_none_for_thin_signal():
    s = PodcastSignal(is_podcast_clip=True, confidence=0.1)
    assert _build_query(s) is None


def test_build_query_uses_topic_when_no_host():
    s = PodcastSignal(
        is_podcast_clip=True, topics=["neuroscience"], confidence=0.4
    )
    q = _build_query(s)
    assert q == "neuroscience"


def test_strength_show_match_baseline():
    s = PodcastSignal(host="Lex Fridman", show="Lex Fridman Podcast")
    ep = {"name": "Random episode"}
    assert _strength(s, ep, show_match=True) > _strength(s, ep, show_match=False)


def test_strength_guest_in_episode_name():
    s = PodcastSignal(host="Lex Fridman", guest="Elon Musk")
    ep = {"name": "Elon Musk on AI and Mars"}
    assert _strength(s, ep, show_match=True) > 0.5


def test_strength_capped_at_95():
    s = PodcastSignal(
        host="Joe Rogan",
        show="JRE",
        guest="Theo Von",
        topic_hint="hunting story",
    )
    ep = {"name": "Theo Von hunting story with Joe Rogan"}
    assert _strength(s, ep, show_match=True) <= 0.95
