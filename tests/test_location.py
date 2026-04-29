from djx.insights.location import detect_locations, woeid_for_country


def test_detects_brazil():
    out = detect_locations(["Visiting Rio next week", "love brazilian funk"])
    countries = dict(out)
    assert countries.get("brazil", 0) >= 1


def test_detects_uk():
    out = detect_locations(["just landed in london", "British weather"])
    assert dict(out).get("united_kingdom", 0) >= 1


def test_handles_empty_and_none():
    out = detect_locations(["", None, "no signal here"])
    assert out == []


def test_woeid_lookup():
    assert woeid_for_country("united_states") == 23424977
    assert woeid_for_country("nonexistent") is None


def test_multiple_countries_in_corpus():
    out = detect_locations([
        "Brazilian funk is fire",
        "UK garage scene",
        "Brazilian samba",
    ])
    keys = dict(out)
    assert keys["brazil"] >= 2
    assert keys["united_kingdom"] >= 1
