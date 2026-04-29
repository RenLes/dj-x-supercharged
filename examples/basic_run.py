"""Minimal scripted run that bypasses the CLI.

Useful when you want to embed dj-x-supercharged in a larger pipeline.
"""

from __future__ import annotations

import asyncio

from djx import (
    HybridAnalyzer,
    Recommender,
    SpotifyClient,
    XClient,
    build_playlist,
)
from djx.auth.token_store import TokenStore
from djx.cache import DiskCache
from djx.config import Config
from djx.recommender.candidates import expand_candidates
from djx.recommender.seeds import build_seeds


async def main() -> None:
    cfg = Config.load()
    store = TokenStore(cfg.tokens_path)
    cache = DiskCache(cfg.cache_dir)

    spotify = SpotifyClient(
        store, client_id=cfg.spotify_client_id, client_secret=cfg.spotify_client_secret
    )
    xc = XClient(store, cache, client_id=cfg.x_client_id, client_secret=cfg.x_client_secret)
    analyzer = HybridAnalyzer(llm=None)  # heuristic-only for this minimal example

    try:
        top = await spotify.top_artists(limit=5)
        artist_analyses: dict[str, list] = {}
        for artist in top:
            user = await xc.find_user_by_username(artist["name"].replace(" ", ""))
            if not user:
                continue
            tweets = await xc.user_tweets(user["id"], max_results=20)
            artist_analyses[artist["name"]] = await analyzer.analyze_batch(
                [t.get("text", "") for t in tweets]
            )

        pool = build_seeds(top, artist_analyses, [])
        candidates = await expand_candidates(spotify, pool)
        ranked = Recommender().rank(candidates, pool, target_count=20)

        me = await spotify.me()
        result = await build_playlist(
            spotify, me["id"], ranked, description="Programmatic run", dry_run=True
        )
        for t in result["tracks"]:
            print(f"{t['score']:>5.2f}  {t['artist']} — {t['name']}")
    finally:
        await spotify.aclose()
        await xc.aclose()


if __name__ == "__main__":
    asyncio.run(main())
