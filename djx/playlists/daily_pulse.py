"""Daily Pulse — last 24h of user signal + global pulse."""

from __future__ import annotations

import datetime as dt

from djx.analyzer.base import BaseAnalyzer
from djx.clients.spotify import SpotifyClient
from djx.clients.x import XClient
from djx.insights.window import iso_window_start
from djx.playlists._pipeline import TweetWindow, gather_window
from djx.playlists.charts import (
    GLOBAL_TOP_50,
    GLOBAL_VIRAL_50,
    REGIONAL_TOP_50,
    REGIONAL_VIRAL_50,
    fetch_chart,
)
from djx.recommender.candidates import TrackCandidate, expand_candidates
from djx.recommender.score import Recommender, ScoredTrack
from djx.recommender.seeds import build_seeds


def daily_name(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return f"Daily Pulse — {today.isoformat()}"


async def build_daily_pulse(
    spotify: SpotifyClient,
    xc: XClient,
    analyzer: BaseAnalyzer,
    *,
    user_id: str,
    top_artists: list[dict],
    track_count: int = 30,
) -> tuple[list[ScoredTrack], TweetWindow]:
    """Compose Daily Pulse candidates + scoring; caller builds the actual playlist."""
    start = iso_window_start(hours=24)
    window = await gather_window(
        xc,
        analyzer,
        user_id=user_id,
        start_time=start,
        window_hours=24,
        include_timeline=True,
        include_trends=True,
        likes_max=100,
        timeline_max=100,
        spotify_for_virality_check=spotify,
    )

    seed_pool = build_seeds(
        top_artists=top_artists,
        artist_analyses={},  # daily mode skips per-artist scrape (too slow for 24h cadence)
        user_likes_analyses=window.all_analyses,
    )
    for name, count in window.viral_artists[:10]:
        seed_pool.artist_weights[name] += min(8, 3 + count)

    candidates: list[TrackCandidate] = await expand_candidates(spotify, seed_pool)

    candidates += await fetch_chart(spotify, GLOBAL_VIRAL_50, seed_label="global_viral", weight=4)
    candidates += await fetch_chart(spotify, GLOBAL_TOP_50, seed_label="global_top", weight=3)

    for country_key, _ in window.locations[:2]:
        if pid := REGIONAL_VIRAL_50.get(country_key):
            candidates += await fetch_chart(
                spotify, pid, seed_label=f"viral:{country_key}", weight=5
            )
        elif pid := REGIONAL_TOP_50.get(country_key):
            candidates += await fetch_chart(
                spotify, pid, seed_label=f"top:{country_key}", weight=4
            )

    ranked = Recommender().rank(
        candidates, seed_pool, target_count=track_count
    )
    return ranked, window


def daily_description(window: TweetWindow, n_tweets: int) -> str:
    parts = [
        f"Daily Pulse for {dt.date.today().isoformat()}.",
        f"Mood: {window.dominant_mood}, energy: {window.dominant_energy}.",
        f"Built from {n_tweets} tweets in the last 24h.",
    ]
    if window.viral_artists:
        names = ", ".join(n for n, _ in window.viral_artists[:3])
        parts.append(f"Trending artists: {names}.")
    if window.locations:
        names = ", ".join(k.replace("_", " ") for k, _ in window.locations[:2])
        parts.append(f"Regions: {names}.")
    if window.trends.music_related:
        parts.append(f"{len(window.trends.music_related)} music trends detected.")
    return " ".join(parts)[:300]
