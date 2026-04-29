from __future__ import annotations

import asyncio
from typing import Any

import httpx

from djx.auth.token_store import TokenStore

API = "https://api.spotify.com/v1"


class SpotifyClient:
    """Async Spotify Web API client. Handles 401 refresh and 429 backoff."""

    def __init__(
        self,
        store: TokenStore,
        *,
        client_id: str,
        client_secret: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ):
        self.store = store
        self.client_id = client_id
        self.client_secret = client_secret
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _headers(self) -> dict[str, str]:
        tokens = self.store.get("spotify")
        if tokens is None:
            raise RuntimeError("No Spotify tokens. Run `djx auth spotify`.")
        if tokens.is_expired():
            from djx.auth import spotify_oauth

            tokens = await spotify_oauth.refresh(
                client_id=self.client_id, client_secret=self.client_secret, store=self.store
            )
        return {"Authorization": f"Bearer {tokens.access_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{API}{path}"
        for attempt in range(4):
            headers = await self._headers()
            kwargs_headers = {**headers, **kwargs.pop("headers", {})}
            r = await self._client.request(method, url, headers=kwargs_headers, **kwargs)
            if r.status_code == 401 and attempt == 0:
                # force refresh on next iteration
                t = self.store.get("spotify")
                if t:
                    t.expires_at = 0
                    self.store.set("spotify", t)
                continue
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", "1"))
                await asyncio.sleep(min(wait, 30))
                continue
            r.raise_for_status()
            if r.status_code == 204 or not r.content:
                return None
            return r.json()
        raise RuntimeError(f"Spotify request failed after retries: {method} {path}")

    # ---- domain methods ----

    async def me(self) -> dict:
        return await self._request("GET", "/me")

    async def top_artists(self, limit: int = 20, time_range: str = "medium_term") -> list[dict]:
        data = await self._request(
            "GET", "/me/top/artists", params={"limit": limit, "time_range": time_range}
        )
        return data.get("items", [])

    async def recently_played(self, limit: int = 50) -> list[dict]:
        data = await self._request("GET", "/me/player/recently-played", params={"limit": limit})
        return data.get("items", [])

    async def search(self, query: str, type_: str = "track", limit: int = 10) -> dict:
        return await self._request(
            "GET", "/search", params={"q": query, "type": type_, "limit": limit}
        )

    async def artist_top_tracks(self, artist_id: str, market: str = "US") -> list[dict]:
        data = await self._request("GET", f"/artists/{artist_id}/top-tracks", params={"market": market})
        return data.get("tracks", [])

    async def related_artists(self, artist_id: str) -> list[dict]:
        try:
            data = await self._request("GET", f"/artists/{artist_id}/related-artists")
            return data.get("artists", [])
        except httpx.HTTPStatusError:
            return []

    async def create_playlist(
        self, user_id: str, name: str, description: str = "", public: bool = False
    ) -> dict:
        return await self._request(
            "POST",
            f"/users/{user_id}/playlists",
            json={"name": name, "description": description, "public": public},
        )

    async def playlist_tracks(self, playlist_id: str, limit: int = 50) -> list[dict]:
        """Fetch tracks from a public playlist (curated charts use this)."""
        data = await self._request(
            "GET",
            f"/playlists/{playlist_id}/tracks",
            params={"limit": limit, "fields": "items(track(uri,id,name,artists(id,name),popularity))"},
        )
        out: list[dict] = []
        for it in data.get("items", []):
            t = it.get("track")
            if t and t.get("uri"):
                out.append(t)
        return out

    async def top_tracks(self, limit: int = 50, time_range: str = "short_term") -> list[dict]:
        """Authenticated user's top tracks. Unrestricted endpoint."""
        data = await self._request(
            "GET", "/me/top/tracks", params={"limit": limit, "time_range": time_range}
        )
        return data.get("items", [])

    async def search_episodes(self, query: str, limit: int = 5, market: str = "US") -> list[dict]:
        """Search Spotify for podcast episodes."""
        r = await self._request(
            "GET",
            "/search",
            params={"q": query, "type": "episode", "limit": limit, "market": market},
        )
        return r.get("episodes", {}).get("items", []) or []

    async def search_shows(self, query: str, limit: int = 5, market: str = "US") -> list[dict]:
        """Search Spotify for podcast shows."""
        r = await self._request(
            "GET",
            "/search",
            params={"q": query, "type": "show", "limit": limit, "market": market},
        )
        return r.get("shows", {}).get("items", []) or []

    async def show_episodes(
        self, show_id: str, limit: int = 10, market: str = "US"
    ) -> list[dict]:
        """List the most recent episodes of a show. Drops None entries (region-locked)."""
        r = await self._request(
            "GET",
            f"/shows/{show_id}/episodes",
            params={"limit": limit, "market": market},
        )
        return [ep for ep in (r.get("items", []) or []) if ep is not None]

    async def add_tracks(self, playlist_id: str, uris: list[str]) -> dict:
        # Spotify max 100 per request
        added: list[str] = []
        for i in range(0, len(uris), 100):
            chunk = uris[i : i + 100]
            await self._request("POST", f"/playlists/{playlist_id}/tracks", json={"uris": chunk})
            added.extend(chunk)
        return {"added": len(added)}
