import time

from djx.cache.disk_cache import DiskCache


def test_set_get_round_trip(tmp_path):
    c = DiskCache(tmp_path)
    c.set("ns", {"k": 1}, {"hello": "world"})
    assert c.get("ns", {"k": 1}, ttl_seconds=60) == {"hello": "world"}


def test_ttl_expiry(tmp_path):
    c = DiskCache(tmp_path)
    c.set("ns", {"k": 1}, "value")
    assert c.get("ns", {"k": 1}, ttl_seconds=0) is None


def test_namespace_isolation(tmp_path):
    c = DiskCache(tmp_path)
    c.set("a", {"k": 1}, "A")
    c.set("b", {"k": 1}, "B")
    assert c.get("a", {"k": 1}, ttl_seconds=60) == "A"
    assert c.get("b", {"k": 1}, ttl_seconds=60) == "B"


def test_clear_specific_namespace(tmp_path):
    c = DiskCache(tmp_path)
    c.set("a", {"k": 1}, "x")
    c.set("b", {"k": 1}, "y")
    c.clear("a")
    assert c.get("a", {"k": 1}, ttl_seconds=60) is None
    assert c.get("b", {"k": 1}, ttl_seconds=60) == "y"


def test_stable_key_independent_of_dict_order(tmp_path):
    c = DiskCache(tmp_path)
    c.set("ns", {"a": 1, "b": 2}, "v")
    # Different insertion order, same logical params:
    assert c.get("ns", {"b": 2, "a": 1}, ttl_seconds=60) == "v"
    _ = time.time()
