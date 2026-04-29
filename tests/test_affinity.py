import datetime as dt

from djx.podcasts.affinity import AffinityStore, normalize_to_100


def test_record_and_score(tmp_path):
    a = AffinityStore.load(tmp_path / "aff.json")
    a.record_signal("host", "Joe Rogan", weight=1.0)
    a.record_signal("host", "Joe Rogan", weight=1.0)
    a.record_signal("host", "Lex Fridman", weight=1.0)
    a.save()
    assert a.score("host", "Joe Rogan") > a.score("host", "Lex Fridman")


def test_persistence_round_trip(tmp_path):
    p = tmp_path / "aff.json"
    a = AffinityStore.load(p)
    a.record_signal("show", "The Joe Rogan Experience", weight=2.0)
    a.save()

    b = AffinityStore.load(p)
    assert len(b.events) == 1
    assert b.score("show", "The Joe Rogan Experience") > 0


def test_recency_decay(tmp_path):
    a = AffinityStore.load(tmp_path / "aff.json")
    # Old event 90 days ago
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)
    a.events.append(type(a.events).__class__()) if False else None
    from djx.podcasts.affinity import Event

    a.events.append(
        Event(
            entity_type="host",
            entity="A",
            weight=1.0,
            created_at=old.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )
    )
    a.record_signal("host", "B", weight=1.0)
    score_old = a.score("host", "A")
    score_new = a.score("host", "B")
    # Half-life is 30 days, so 90 days ago is ~1/8 weight
    assert score_new > score_old * 4


def test_top_n(tmp_path):
    a = AffinityStore.load(tmp_path / "aff.json")
    for _ in range(5):
        a.record_signal("topic", "comedy")
    for _ in range(3):
        a.record_signal("topic", "ai")
    a.record_signal("topic", "music")

    top = a.top("topic", n=2)
    names = [n for n, _, _ in top]
    assert names[0] == "comedy"
    assert "ai" in names


def test_normalize_to_100():
    rows = [("a", 10.0, 5), ("b", 5.0, 3), ("c", 1.0, 1)]
    normed = normalize_to_100(rows)
    assert normed[0] == ("a", 100, 5)
    assert normed[1][1] == 50
    assert normed[2][1] == 10


def test_similar_host_boost(tmp_path):
    a = AffinityStore.load(tmp_path / "aff.json")
    # Lots of likes on Lex Fridman
    for _ in range(5):
        a.record_signal("host", "Lex Fridman", weight=1.0)
    direct = a.score("host", "Lex Fridman")
    # Joe Rogan is similar; with boost should get a fraction of Lex's score
    rogan_boosted = a.host_score_with_similarity("Joe Rogan")
    assert 0 < rogan_boosted < direct


def test_dedupe_within_hour(tmp_path):
    a = AffinityStore.load(tmp_path / "aff.json")
    for _ in range(5):
        a.record_signal("host", "Joe Rogan")
    a.deduplicate_by_tweet_window(hours=1)
    # All recorded in same hour ⇒ collapses to 1
    assert sum(1 for e in a.events if e.entity == "Joe Rogan") == 1
