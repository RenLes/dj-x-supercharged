"""Mood Mirror — playlist that matches the dominant mood from recent activity."""

from __future__ import annotations

import datetime as dt

from djx.analyzer.base import BaseAnalyzer
from djx.clients.spotify import SpotifyClient
from djx.clients.x import XClient
from djx.insights.window import iso_window_start
from djx.playlists._pipeline import TweetWindow, gather_window
from djx.recommender.candidates import TrackCandidate
from djx.recommender.score import Recommender, ScoredTrack
from djx.recommender.seeds import SeedPool

# Mood -> list of search-friendly genres / vibe keywords. We can't use audio-features
# (restricted), so we steer Spotify search via genre/keyword queries instead.
MOOD_QUERIES: dict[str, list[str]] = {
    "hype": ["genre:hip-hop", "genre:trap", "genre:rap", "banger", "energy", "anthem"],
    "chill": ["genre:lo-fi", "genre:indie", "genre:ambient", "chill", "calm", "mellow"],
    "dark": ["genre:industrial", "genre:gothic", "moody", "haunting", "melancholy", "dark"],
    "energetic": ["genre:dance", "genre:edm", "genre:house", "workout", "uplifting", "energy"],
    "romantic": ["genre:r-n-b", "genre:soul", "love", "ballad", "romance", "intimate"],
    "aggressive": ["genre:metal", "genre:punk", "rage", "intense", "aggressive", "hardcore"],
    "neutral": ["genre:pop", "genre:indie", "genre:rock", "popular", "trending", "fresh"],
}


def mood_mirror_name(mood: str, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return f"Mood Mirror — {mood.title()} — {today.isoformat()}"


async def build_mood_mirror(
    spotify: SpotifyClient,
    xc: XClient,
    analyzer: BaseAnalyzer,
    *,
    user_id: str,
    track_count: int = 25,
    hours: int = 24,
) -> tuple[list[ScoredTrack], TweetWindow, str]:
    start = iso_window_start(hours=hours)
    window = await gather_window(
        xc, analyzer, user_id=user_id, start_time=start,
        window_hours=hours, likes_max=80, timeline_max=80,
        spotify_for_virality_check=spotify,
    )
    mood = window.dominant_mood
    queries = MOOD_QUERIES.get(mood, MOOD_QUERIES["neutral"])

    candidates: list[TrackCandidate] = []
    seen: set[str] = set()
    for q in queries:
        try:
            r = await spotify.search(q, type_="track", limit=10)
        except Exception:
            continue
        for t in r.get("tracks", {}).get("items", []):
            uri = t.get("uri")
            if not uri or uri in seen:
                continue
            seen.add(uri)
            artists = t.get("artists", []) or [{}]
            primary = artists[0]
            candidates.append(
                TrackCandidate(
                    uri=uri,
                    track_id=t["id"],
                    name=t["name"],
                    artist_name=primary.get("name", "Unknown"),
                    artist_id=primary.get("id", ""),
                    popularity=int(t.get("popularity") or 0),
                    seed_artist=f"mood:{mood}",
                    seed_weight=4,
                )
            )

    ranked = Recommender().rank(candidates, SeedPool(), target_count=track_count)
    return ranked, window, mood
