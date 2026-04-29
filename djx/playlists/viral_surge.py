"""Viral Surge — heavily prioritize artists/tracks surging across recent X activity."""

from __future__ import annotations

import datetime as dt

from djx.analyzer.base import BaseAnalyzer
from djx.clients.spotify import SpotifyClient
from djx.clients.x import XClient
from djx.insights.window import iso_window_start
from djx.playlists._pipeline import TweetWindow, gather_window
from djx.playlists.charts import GLOBAL_VIRAL_50, fetch_chart
from djx.recommender.candidates import TrackCandidate
from djx.recommender.score import Recommender, ScoredTrack
from djx.recommender.seeds import SeedPool


def viral_surge_name(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return f"Viral Surge — {today.isoformat()}"


async def build_viral_surge(
    spotify: SpotifyClient,
    xc: XClient,
    analyzer: BaseAnalyzer,
    *,
    user_id: str,
    track_count: int = 25,
    hours: int = 48,
) -> tuple[list[ScoredTrack], TweetWindow]:
    start = iso_window_start(hours=hours)
    window = await gather_window(
        xc, analyzer, user_id=user_id, start_time=start,
        window_hours=hours, likes_max=80, timeline_max=80,
        spotify_for_virality_check=spotify,
    )

    pool = SeedPool()
    for name, count in window.viral_artists[:20]:
        pool.artist_weights[name] += min(10, 4 + count)

    candidates: list[TrackCandidate] = []
    seen: set[str] = set()
    for name, weight in pool.artist_weights.most_common(20):
        try:
            r = await spotify.search(f'artist:"{name}"', type_="track", limit=5)
        except Exception:
            continue
        for t in r.get("tracks", {}).get("items", []):
            uri = t.get("uri")
            if not uri or uri in seen:
                continue
            seen.add(uri)
            track_artists = t.get("artists", []) or [{}]
            if not any(a.get("name", "").lower() == name.lower() for a in track_artists):
                continue
            primary = track_artists[0]
            candidates.append(
                TrackCandidate(
                    uri=uri,
                    track_id=t["id"],
                    name=t["name"],
                    artist_name=primary.get("name", name),
                    artist_id=primary.get("id", ""),
                    popularity=int(t.get("popularity") or 0),
                    seed_artist=name,
                    seed_weight=weight,
                )
            )

    candidates += await fetch_chart(spotify, GLOBAL_VIRAL_50, seed_label="global_viral", weight=4)

    # Fallback: when X feed has no detectable viral artists (or all got filtered)
    # pull user's recent top tracks so we still produce a playlist.
    if len(candidates) < track_count:
        try:
            top = await spotify.top_tracks(limit=50, time_range="short_term")
        except Exception:
            top = []
        seen_uris = {c.uri for c in candidates}
        for t in top:
            uri = t.get("uri")
            if not uri or uri in seen_uris:
                continue
            seen_uris.add(uri)
            artists = t.get("artists", []) or [{}]
            primary = artists[0]
            candidates.append(
                TrackCandidate(
                    uri=uri,
                    track_id=t.get("id", ""),
                    name=t.get("name", ""),
                    artist_name=primary.get("name", "Unknown"),
                    artist_id=primary.get("id", ""),
                    popularity=int(t.get("popularity") or 0),
                    seed_artist="user_top",
                    seed_weight=3,
                )
            )

    ranked = Recommender().rank(candidates, pool, target_count=track_count)
    return ranked, window
