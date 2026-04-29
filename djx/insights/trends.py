from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

MUSIC_TREND_RE = re.compile(
    r"\b("
    r"song|album|track|single|ep|tour|concert|festival|"
    r"#1|chart|stream|streaming|debuts?|drops?|premiere|"
    r"NewMusicFriday|NowPlaying|playlist|bops?|banger|"
    r"vibes?|hits?|anthem|earworm|mixtape|spotify|"
    r"audio|sound|beat|dj|remix|cover|feature|feat|"
    r"music|musician|artists?|band|rapper|singer|vocalist"
    r")\b",
    re.IGNORECASE,
)
EVENT_RE = re.compile(
    r"\b(super\s*bowl|world\s*cup|grammy|oscar|election|olympic|"
    r"weather|hurricane|earthquake|festival|wedding|funeral)\b",
    re.IGNORECASE,
)


@dataclass
class TrendInsight:
    music_related: list[dict]      # trend dicts that look music-relevant
    event_signals: list[dict]      # trend dicts that signal a live event
    raw_count: int
    top_categories: list[tuple[str, int]]


def _post_count_to_int(s: str | None) -> int:
    """X returns post counts like '1.2K posts', '186K posts', '2.3M posts'."""
    if not s:
        return 0
    m = re.match(r"\s*([\d.]+)\s*([KMB]?)", s, re.IGNORECASE)
    if not m:
        return 0
    n = float(m.group(1))
    mul = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2).upper()]
    return int(n * mul)


def summarize_trends(trends: list[dict]) -> TrendInsight:
    """Classify a personalized_trends payload into music vs event signals."""
    music: list[dict] = []
    events: list[dict] = []
    cats: Counter[str] = Counter()

    for t in trends:
        name = t.get("trend_name", "") or ""
        cat = t.get("category", "") or ""
        cats[cat] += 1
        text = f"{name} {cat}"
        score = _post_count_to_int(t.get("post_count"))
        enriched = {**t, "post_count_int": score}
        if MUSIC_TREND_RE.search(text) or cat.lower() in {"music", "entertainment"}:
            music.append(enriched)
        if EVENT_RE.search(text):
            events.append(enriched)

    music.sort(key=lambda x: x.get("post_count_int", 0), reverse=True)
    events.sort(key=lambda x: x.get("post_count_int", 0), reverse=True)
    return TrendInsight(
        music_related=music,
        event_signals=events,
        raw_count=len(trends),
        top_categories=cats.most_common(5),
    )
