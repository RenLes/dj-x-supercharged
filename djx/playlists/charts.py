"""Curated Spotify Top 50 / Viral 50 playlist IDs as a stand-in for charts.

Spotify has no public "what's hot today" API, but their editorial Top 50 and
Viral 50 playlists are public and update daily. We fetch those as a chart proxy.
"""

from __future__ import annotations

from djx.clients.spotify import SpotifyClient
from djx.recommender.candidates import TrackCandidate

GLOBAL_TOP_50 = "37i9dQZEVXbMDoHDwVN2tF"
GLOBAL_VIRAL_50 = "37i9dQZEVXbLiRSasKsNU9"

# Per-country "Top 50 - <Country>" playlist IDs (Spotify-curated, public).
REGIONAL_TOP_50: dict[str, str] = {
    "united_states": "37i9dQZEVXbLRQDuF5jeBp",
    "united_kingdom": "37i9dQZEVXbLnolsZ8PSNw",
    "canada": "37i9dQZEVXbKj23U1GF4IR",
    "australia": "37i9dQZEVXbJPcfkRz0wJ0",
    "brazil": "37i9dQZEVXbMXbN3EUUhlg",
    "mexico": "37i9dQZEVXbO3qyFxbkOE1",
    "germany": "37i9dQZEVXbJiZcmkrIHGU",
    "france": "37i9dQZEVXbIPWwFssbupI",
    "spain": "37i9dQZEVXbNFJfN1Vw8d9",
    "italy": "37i9dQZEVXbIQnj7RRhdSX",
    "japan": "37i9dQZEVXbKXQ4mDTEBXq",
    "south_korea": "37i9dQZEVXbNxXF4SkHj9F",
    "india": "37i9dQZEVXbLZ52XmnySJg",
    "nigeria": "37i9dQZEVXbKY7jLzlJ11V",
    "new_zealand": "37i9dQZEVXbM8SIrkERIYl",
}

REGIONAL_VIRAL_50: dict[str, str] = {
    "united_states": "37i9dQZEVXbKuaTI1Z1Afx",
    "united_kingdom": "37i9dQZEVXbL3DLHfQeDmV",
    "brazil": "37i9dQZEVXbJqfMFK4d691",
    "mexico": "37i9dQZEVXbKVCoWLD4Jwl",
}


async def fetch_chart(
    spotify: SpotifyClient, playlist_id: str, *, seed_label: str, weight: int = 4
) -> list[TrackCandidate]:
    """Pull tracks from a curated playlist and wrap them as TrackCandidates."""
    candidates: list[TrackCandidate] = []
    try:
        tracks = await spotify.playlist_tracks(playlist_id, limit=50)
    except Exception:
        return candidates
    for t in tracks:
        try:
            uri = t["uri"]
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
                    seed_artist=seed_label,
                    seed_weight=weight,
                )
            )
        except (KeyError, TypeError):
            continue
    return candidates
