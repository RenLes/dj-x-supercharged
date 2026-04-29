from __future__ import annotations

import asyncio
from typing import Any

import httpx

from djx.auth.token_store import TokenStore
from djx.cache import DiskCache
from djx.logging import console

API = "https://api.twitter.com/2"


class XAccessLimited(RuntimeError):
    """Raised when the X tier doesn't permit a given endpoint (HTTP 403)."""


class XClient:
    """Async X API v2 client. 24h disk cache for read endpoints + 403 detection."""

    def __init__(
        self,
        store: TokenStore,
        cache: DiskCache,
        *,
        client_id: str,
        client_secret: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ):
        self.store = store
        self.cache = cache
        self.client_id = client_id
        self.client_secret = client_secret
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self.degraded: set[str] = set()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _headers(self) -> dict[str, str]:
        tokens = self.store.get("x")
        if tokens is None:
            raise RuntimeError("No X tokens. Run `djx auth x`.")
        if tokens.is_expired():
            from djx.auth import x_oauth

            tokens = await x_oauth.refresh(
                client_id=self.client_id, client_secret=self.client_secret, store=self.store
            )
        return {"Authorization": f"Bearer {tokens.access_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{API}{path}"
        for attempt in range(4):
            headers = await self._headers()
            kwargs_headers = {**headers, **kwargs.pop("headers", {})}
            r = await self._client.request(method, url, headers=kwargs_headers, **kwargs)
            if r.status_code == 401 and attempt == 0:
                t = self.store.get("x")
                if t:
                    t.expires_at = 0
                    self.store.set("x", t)
                continue
            if r.status_code in (402, 403):
                self.degraded.add(path.split("?")[0].rstrip("/"))
                code = r.status_code
                console.print(
                    f"[yellow]X {code} on {path} — your tier doesn't include this endpoint. Skipping.[/yellow]"
                )
                raise XAccessLimited(path)
            if r.status_code == 429:
                wait = float(r.headers.get("x-rate-limit-reset", "0"))
                if wait:
                    import time

                    sleep = max(1.0, wait - time.time())
                else:
                    sleep = float(r.headers.get("Retry-After", "60"))
                console.print(f"[yellow]X 429 — sleeping {min(sleep, 60):.0f}s[/yellow]")
                await asyncio.sleep(min(sleep, 60))
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"X request failed after retries: {method} {path}")

    # ---- domain methods (cached) ----

    async def me(self) -> dict:
        return (await self._request("GET", "/users/me")).get("data", {})

    async def find_user_by_username(self, username: str) -> dict | None:
        cached = self.cache.get("x_user", {"u": username.lower()}, ttl_seconds=60 * 60 * 24 * 30)
        if cached is not None:
            return cached or None
        try:
            r = await self._request("GET", f"/users/by/username/{username}")
        except XAccessLimited:
            return None
        except httpx.HTTPStatusError:
            self.cache.set("x_user", {"u": username.lower()}, {})
            return None
        data = r.get("data")
        self.cache.set("x_user", {"u": username.lower()}, data or {})
        return data

    @staticmethod
    def _sanitize_query(query: str) -> str:
        """X /users/search 400s on punctuation (e.g. 'Dr. Dre'). Strip non-alnum."""
        import re as _re

        cleaned = _re.sub(r"[^A-Za-z0-9 ]+", " ", query or "").strip()
        cleaned = _re.sub(r"\s+", " ", cleaned)
        return cleaned[:32]

    async def search_user(self, query: str, max_results: int = 5) -> list[dict]:
        clean = self._sanitize_query(query)
        if not clean:
            return []
        cached = self.cache.get("x_user_search", {"q": clean.lower()}, ttl_seconds=60 * 60 * 24 * 7)
        if cached is not None:
            return cached
        try:
            r = await self._request(
                "GET", "/users/search", params={"query": clean, "max_results": max_results}
            )
        except XAccessLimited:
            return []
        except httpx.HTTPStatusError:
            self.cache.set("x_user_search", {"q": clean.lower()}, [])
            return []
        data = r.get("data", []) or []
        self.cache.set("x_user_search", {"q": clean.lower()}, data)
        return data

    async def user_tweets(self, user_id: str, max_results: int = 100) -> list[dict]:
        cached = self.cache.get("x_user_tweets", {"id": user_id}, ttl_seconds=60 * 60 * 24)
        if cached is not None:
            return cached
        try:
            r = await self._request(
                "GET",
                f"/users/{user_id}/tweets",
                params={
                    "max_results": max_results,
                    "tweet.fields": "created_at,text,entities",
                    "exclude": "retweets,replies",
                },
            )
        except XAccessLimited:
            self.cache.set("x_user_tweets", {"id": user_id}, [])
            return []
        data = r.get("data", []) or []
        self.cache.set("x_user_tweets", {"id": user_id}, data)
        return data

    async def liked_tweets(
        self,
        user_id: str,
        max_results: int = 50,
    ) -> list[dict]:
        """Fetch the authenticated user's liked tweets.

        Note: this endpoint does NOT accept a `start_time` parameter — it always
        returns the most recent likes. Time-window filtering happens client-side
        via ``djx.insights.window.within_window``.
        """
        key = {"id": user_id}
        ttl = 60 * 60 * 6
        cached = self.cache.get("x_liked", key, ttl_seconds=ttl)
        if cached is not None:
            return cached
        params: dict = {"max_results": max_results, "tweet.fields": "created_at,text,entities"}
        try:
            r = await self._request("GET", f"/users/{user_id}/liked_tweets", params=params)
        except XAccessLimited:
            self.cache.set("x_liked", key, [])
            return []
        data = r.get("data", []) or []
        self.cache.set("x_liked", key, data)
        return data

    async def home_timeline(
        self,
        user_id: str,
        max_results: int = 50,
        *,
        start_time: str | None = None,
    ) -> list[dict]:
        """Reverse-chronological home timeline as a proxy for recent activity."""
        key = {"id": user_id, "start": start_time or ""}
        ttl = 60 * 60  # 1h — timeline moves fast
        cached = self.cache.get("x_timeline", key, ttl_seconds=ttl)
        if cached is not None:
            return cached
        params: dict = {
            "max_results": max_results,
            "tweet.fields": "created_at,text,entities,public_metrics",
        }
        if start_time:
            params["start_time"] = start_time
        try:
            r = await self._request(
                "GET", f"/users/{user_id}/timelines/reverse_chronological", params=params
            )
        except XAccessLimited:
            self.cache.set("x_timeline", key, [])
            return []
        data = r.get("data", []) or []
        self.cache.set("x_timeline", key, data)
        return data

    async def personalized_trends(self) -> list[dict]:
        """Per-user trending topics. Tier-gated; degrades to [] on 403."""
        cached = self.cache.get("x_ptrends", {}, ttl_seconds=60 * 30)
        if cached is not None:
            return cached
        try:
            r = await self._request("GET", "/users/personalized_trends")
        except XAccessLimited:
            self.cache.set("x_ptrends", {}, [])
            return []
        data = r.get("data", []) or []
        self.cache.set("x_ptrends", {}, data)
        return data

    async def trends_by_woeid(self, woeid: int) -> list[dict]:
        """Location-based trends. WOEID 1 = worldwide; 23424977 = USA; etc."""
        cached = self.cache.get("x_woeid", {"w": woeid}, ttl_seconds=60 * 30)
        if cached is not None:
            return cached
        try:
            r = await self._request("GET", f"/trends/by/woeid/{woeid}")
        except XAccessLimited:
            self.cache.set("x_woeid", {"w": woeid}, [])
            return []
        data = r.get("data", []) or []
        self.cache.set("x_woeid", {"w": woeid}, data)
        return data
