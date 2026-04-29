from __future__ import annotations

from dataclasses import dataclass

from djx.clients.spotify import SpotifyClient
from djx.recommender.seeds import SeedPool


@dataclass
class TrackCandidate:
    uri: str
    track_id: str
    name: str
    artist_name: str
    artist_id: str
    popularity: int
    seed_artist: str
    seed_weight: int


async def expand_candidates(
    spotify: SpotifyClient,
    pool: SeedPool,
    *,
    top_seed_artists: int = 15,
    tracks_per_artist: int = 8,
    include_user_top_tracks: bool = True,
) -> list[TrackCandidate]:
    """Build candidate tracks for the recommender.

    Uses Spotify endpoints that are NOT restricted by Extended Quota Mode:
      - GET /v1/search?type=track&q=artist:"<name>"  (unrestricted)
      - GET /v1/me/top/tracks                         (unrestricted)

    Avoids the restricted endpoints that 403 on dev-mode apps:
      - /v1/artists/{id}/top-tracks
      - /v1/artists/{id}/related-artists
      - /v1/recommendations
    """
    candidates: list[TrackCandidate] = []
    seen_uris: set[str] = set()

    seeds = pool.artist_weights.most_common(top_seed_artists)
    for name, weight in seeds:
        try:
            r = await spotify.search(f'artist:"{name}"', type_="track", limit=tracks_per_artist)
        except Exception:
            continue
        for t in r.get("tracks", {}).get("items", []):
            uri = t.get("uri")
            if not uri or uri in seen_uris:
                continue
            track_artists = t.get("artists", []) or [{}]
            primary = track_artists[0]
            # Only keep if the seed artist is actually on the track (avoids name collisions).
            if not any(a.get("name", "").lower() == name.lower() for a in track_artists):
                continue
            seen_uris.add(uri)
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

    if include_user_top_tracks:
        try:
            r = await spotify._request(
                "GET", "/me/top/tracks", params={"limit": 30, "time_range": "short_term"}
            )
            for t in r.get("items", []):
                uri = t.get("uri")
                if not uri or uri in seen_uris:
                    continue
                track_artists = t.get("artists", []) or [{}]
                primary = track_artists[0]
                seen_uris.add(uri)
                candidates.append(
                    TrackCandidate(
                        uri=uri,
                        track_id=t["id"],
                        name=t["name"],
                        artist_name=primary.get("name", "Unknown"),
                        artist_id=primary.get("id", ""),
                        popularity=int(t.get("popularity") or 0),
                        seed_artist=primary.get("name", "user_top"),
                        seed_weight=4,  # decent weight, but below tweet-boosted seeds
                    )
                )
        except Exception:
            pass

    # Track-title hints from analyzed tweets — a track named in a tweet should rank higher
    # if it actually exists on Spotify.
    for title, hint_weight in pool.track_hints.most_common(10):
        try:
            r = await spotify.search(f'track:"{title}"', type_="track", limit=2)
        except Exception:
            continue
        for t in r.get("tracks", {}).get("items", []):
            uri = t.get("uri")
            if not uri or uri in seen_uris:
                continue
            track_artists = t.get("artists", []) or [{}]
            primary = track_artists[0]
            seen_uris.add(uri)
            candidates.append(
                TrackCandidate(
                    uri=uri,
                    track_id=t["id"],
                    name=t["name"],
                    artist_name=primary.get("name", "Unknown"),
                    artist_id=primary.get("id", ""),
                    popularity=int(t.get("popularity") or 0),
                    seed_artist=primary.get("name", "tweet_hint"),
                    seed_weight=int(hint_weight) + 2,
                )
            )

    return candidates
