"""Persistent affinity scoring for podcast hosts, shows, and topics.

The score for an entity is the sum of recency-weighted contributions from each
"like" event we've recorded. Stored as JSON at `~/.djx/affinity.json`.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from djx.podcasts.known_hosts import SIMILAR_HOSTS

HALF_LIFE_DAYS = 30.0
SIMILAR_BOOST = 0.4  # multiplier for similar hosts when computing a host's score


@dataclass
class Event:
    """A single like-event contributing to affinity."""

    entity_type: str  # 'host' | 'show' | 'topic'
    entity: str
    weight: float
    created_at: str  # RFC3339 UTC


@dataclass
class AffinityStore:
    path: Path
    events: list[Event] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> AffinityStore:
        path = Path(path)
        if not path.exists():
            return cls(path=path, events=[])
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            events = [Event(**e) for e in raw.get("events", [])]
        except (json.JSONDecodeError, OSError, TypeError):
            events = []
        return cls(path=path, events=events)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"events": [e.__dict__ for e in self.events]}, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    # ---- mutation ----

    def record_signal(self, entity_type: str, entity: str, weight: float = 1.0) -> None:
        """Append an event with current UTC timestamp."""
        ts = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        self.events.append(
            Event(entity_type=entity_type, entity=entity, weight=float(weight), created_at=ts)
        )

    def deduplicate_by_tweet_window(self, hours: int = 1) -> None:
        """Optional: drop events that look like exact duplicates within a window."""
        seen: dict[tuple[str, str, str], None] = {}
        kept: list[Event] = []
        for e in self.events:
            key = (e.entity_type, e.entity.lower(), e.created_at[:13])  # by hour
            if key in seen:
                continue
            seen[key] = None
            kept.append(e)
        self.events = kept

    # ---- query ----

    def score(self, entity_type: str, entity: str, *, now: dt.datetime | None = None) -> float:
        """Total recency-weighted score for one entity."""
        now = now or dt.datetime.now(dt.timezone.utc)
        total = 0.0
        for e in self.events:
            if e.entity_type != entity_type or e.entity.lower() != entity.lower():
                continue
            total += _recency_weighted(e, now)
        return round(total, 3)

    def top(
        self, entity_type: str, n: int = 10, *, now: dt.datetime | None = None
    ) -> list[tuple[str, float, int]]:
        """Top entities by score, returning (name, score, raw_event_count)."""
        now = now or dt.datetime.now(dt.timezone.utc)
        agg: dict[str, list[float]] = {}
        for e in self.events:
            if e.entity_type != entity_type:
                continue
            agg.setdefault(e.entity, []).append(_recency_weighted(e, now))
        ranked = sorted(
            ((name, round(sum(ws), 3), len(ws)) for name, ws in agg.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:n]

    def host_score_with_similarity(
        self, host: str, *, now: dt.datetime | None = None
    ) -> float:
        """Score for a host, plus a fraction of similar hosts' scores."""
        now = now or dt.datetime.now(dt.timezone.utc)
        primary = self.score("host", host, now=now)
        bonus = 0.0
        for similar in SIMILAR_HOSTS.get(host, ()):
            bonus += SIMILAR_BOOST * self.score("host", similar, now=now)
        return round(primary + bonus, 3)


def _recency_weighted(e: Event, now: dt.datetime) -> float:
    try:
        when = dt.datetime.fromisoformat(e.created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return e.weight
    age_days = max((now - when).total_seconds() / 86400.0, 0.0)
    decay = math.exp(-math.log(2) * age_days / HALF_LIFE_DAYS)
    return e.weight * decay


def normalize_to_100(scores: list[tuple[str, float, int]]) -> list[tuple[str, int, int]]:
    """Convert raw scores to a 0-100 scale anchored on the top entry."""
    if not scores:
        return []
    top = max(s for _, s, _ in scores) or 1.0
    return [(name, round(s / top * 100), n) for name, s, n in scores]
