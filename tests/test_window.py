import datetime as dt

from djx.insights.window import iso_now, iso_window_start, within_window


def test_iso_now_format():
    s = iso_now()
    # YYYY-MM-DDTHH:MM:SSZ
    assert s.endswith("Z")
    dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_iso_window_start_is_in_past():
    now = dt.datetime.now(dt.timezone.utc)
    start = dt.datetime.fromisoformat(iso_window_start(hours=24).replace("Z", "+00:00"))
    delta = (now - start).total_seconds()
    assert 23.5 * 3600 <= delta <= 24.5 * 3600


def test_within_window_recent():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    assert within_window({"created_at": now}, hours=24) is True


def test_within_window_old():
    long_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)).isoformat().replace("+00:00", "Z")
    assert within_window({"created_at": long_ago}, hours=24) is False


def test_within_window_missing_field():
    assert within_window({}, hours=24) is False


def test_within_window_garbage():
    assert within_window({"created_at": "not-a-date"}, hours=24) is False
