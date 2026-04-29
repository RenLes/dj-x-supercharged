from __future__ import annotations

import datetime as dt


def iso_now() -> str:
    """Current UTC time as RFC3339 string (X API format)."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_window_start(hours: int = 24) -> str:
    """Start of a rolling time window N hours ago, as RFC3339 string."""
    start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def within_window(tweet: dict, hours: int) -> bool:
    """True if the tweet's `created_at` is within the last N hours."""
    ts = tweet.get("created_at")
    if not ts:
        return False
    try:
        when = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    return (dt.datetime.now(dt.timezone.utc) - when).total_seconds() <= hours * 3600
