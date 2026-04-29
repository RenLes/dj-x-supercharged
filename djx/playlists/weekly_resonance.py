"""Weekly Resonance — last 7 days, broader sweep including artist scrapes."""

from __future__ import annotations

import datetime as dt

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.schema import TweetAnalysis
from djx.clients.spotify import SpotifyClient
from djx.clients.x import XAccessLimited, XClient
from djx.insights.window import iso_window_start, within_window
from djx.playlists._pipeline import TweetWindow, gather_window
from djx.playlists.charts import (
    GLOBAL_TOP_50,
    REGIONAL_TOP_50,
    fetch_chart,
)
from djx.recommender.candidates import TrackCandidate, expand_candidates
from djx.recommender.score import Recommender, ScoredTrack
from djx.recommender.seeds import build_seeds


def weekly_name(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return f"Weekly Resonance — {today.isoformat()}"


async def build_weekly_resonance(
    spotify: SpotifyClient,
    xc: XClient,
    analyzer: BaseAnalyzer,
    *,
    user_id: str,
    top_artists: list[dict],
    track_count: int = 50,
    scrape_artist_tweets: bool = True,
) -> tuple[list[ScoredTrack], TweetWindow]:
    start = iso_window_start(hours=24 * 7)
    window = await gather_window(
        xc,
        analyzer,
        user_id=user_id,
        start_time=start,
        window_hours=24 * 7,
        include_timeline=True,
        include_trends=True,
        likes_max=100,
        timeline_max=100,
        spotify_for_virality_check=spotify,
    )

    artist_analyses: dict[str, list[TweetAnalysis]] = {}
    if scrape_artist_tweets:
        for artist in top_artists[:10]:
            handle = artist["name"].replace(" ", "")
            user = await xc.find_user_by_username(handle)
            if user is None:
                hits = await xc.search_user(artist["name"], max_results=1)
                user = hits[0] if hits else None
            if not user or not user.get("id"):
                continue
            try:
                tweets = await xc.user_tweets(user["id"], max_results=50)
            except XAccessLimited:
                tweets = []
            tweets = [t for t in tweets if within_window(t, hours=24 * 7)]
            artist_analyses[artist["name"]] = await analyzer.analyze_batch(
                [t.get("text", "") for t in tweets]
            )

    seed_pool = build_seeds(
        top_artists=top_artists,
        artist_analyses=artist_analyses,
        user_likes_analyses=window.all_analyses,
    )
    for name, count in window.viral_artists[:15]:
        seed_pool.artist_weights[name] += min(6, 2 + count)

    candidates: list[TrackCandidate] = await expand_candidates(
        spotify, seed_pool, top_seed_artists=20, tracks_per_artist=10
    )
    candidates += await fetch_chart(spotify, GLOBAL_TOP_50, seed_label="global_top", weight=3)
    for country_key, _ in window.locations[:3]:
        if pid := REGIONAL_TOP_50.get(country_key):
            candidates += await fetch_chart(
                spotify, pid, seed_label=f"top:{country_key}", weight=4
            )

    ranked = Recommender().rank(candidates, seed_pool, target_count=track_count)
    return ranked, window


def weekly_description(window: TweetWindow, n_tweets: int) -> str:
    parts = [
        f"Weekly Resonance for week ending {dt.date.today().isoformat()}.",
        f"Mood: {window.dominant_mood}, energy: {window.dominant_energy}.",
        f"Built from {n_tweets} tweets across 7 days.",
    ]
    if window.viral_artists:
        names = ", ".join(n for n, _ in window.viral_artists[:5])
        parts.append(f"Recurring artists: {names}.")
    if window.locations:
        names = ", ".join(k.replace("_", " ") for k, _ in window.locations[:3])
        parts.append(f"Regions: {names}.")
    return " ".join(parts)[:300]
