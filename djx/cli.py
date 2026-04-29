from __future__ import annotations

import asyncio
import datetime as dt
import json

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from djx import __version__
from djx.analyzer.grok import GrokAnalyzer
from djx.analyzer.hybrid import HybridAnalyzer
from djx.auth import spotify_oauth, x_oauth
from djx.auth.token_store import TokenStore
from djx.cache import DiskCache
from djx.clients.spotify import SpotifyClient
from djx.clients.x import XClient
from djx.config import Config
from djx.logging import console, log_activity
from djx.playlists.daily_pulse import build_daily_pulse, daily_description, daily_name
from djx.playlists.mood_mirror import build_mood_mirror, mood_mirror_name
from djx.playlists.viral_surge import build_viral_surge, viral_surge_name
from djx.playlists.weekly_resonance import (
    build_weekly_resonance,
    weekly_description,
    weekly_name,
)
from djx.recommender.candidates import expand_candidates
from djx.recommender.playlist import build_playlist, playlist_description, playlist_name
from djx.recommender.score import Recommender
from djx.recommender.seeds import build_seeds

app = typer.Typer(
    name="djx",
    help="Hybrid Spotify + X playlist generator. See https://github.com/RenLes/dj-x-supercharged",
    no_args_is_help=True,
    add_completion=False,
)
auth_app = typer.Typer(help="OAuth flows for Spotify and X.")
app.add_typer(auth_app, name="auth")
podcasts_app = typer.Typer(help="Podcast Pulse — clip-to-episode resolver + affinity engine.")
app.add_typer(podcasts_app, name="podcasts")


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"dj-x-supercharged {__version__}")


@auth_app.command("spotify")
def auth_spotify() -> None:
    """Authorize Spotify and cache tokens."""
    cfg = Config.load()
    store = TokenStore(cfg.tokens_path)
    asyncio.run(
        spotify_oauth.authorize(
            client_id=cfg.spotify_client_id,
            client_secret=cfg.spotify_client_secret,
            redirect_uri=cfg.spotify_redirect_uri,
            store=store,
            vercel_fallback_url=cfg.vercel_fallback_url,
        )
    )
    console.print("[green]Spotify tokens saved.[/green]")


@auth_app.command("x")
def auth_x() -> None:
    """Authorize X (Twitter) and cache tokens."""
    cfg = Config.load()
    store = TokenStore(cfg.tokens_path)
    asyncio.run(
        x_oauth.authorize(
            client_id=cfg.x_client_id,
            client_secret=cfg.x_client_secret,
            redirect_uri=cfg.x_redirect_uri,
            store=store,
            vercel_fallback_url=cfg.vercel_fallback_url,
        )
    )
    console.print("[green]X tokens saved.[/green]")


@auth_app.command("status")
def auth_status() -> None:
    """Show cached token validity for both providers."""
    cfg = Config.load()
    store = TokenStore(cfg.tokens_path)
    table = Table("provider", "status")
    for provider, status in store.status().items():
        color = {"valid": "green", "expired": "yellow", "missing": "red"}[status]
        table.add_row(provider, f"[{color}]{status}[/{color}]")
    console.print(table)


@app.command("clear-cache")
def clear_cache(
    namespace: str = typer.Option("", help="Specific namespace to clear (default: all)"),
) -> None:
    """Clear the on-disk cache."""
    cfg = Config.load()
    cache = DiskCache(cfg.cache_dir)
    n = cache.clear(namespace or None)
    console.print(f"[green]Cleared {n} cache file(s).[/green]")


@app.command()
def run(
    max_artists: int = typer.Option(20, help="How many top artists to scan"),
    track_count: int = typer.Option(30, help="Tracks in the final playlist"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print playlist; skip Spotify create"),
    public: bool = typer.Option(False, help="Create as public playlist (default private)"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Heuristic-only analyzer (skip Grok)"),
) -> None:
    """Run the original Hybrid Vibes pipeline."""
    asyncio.run(_run_async(max_artists, track_count, dry_run, public, no_llm))


def _make_analyzer(cfg: Config, no_llm: bool) -> HybridAnalyzer:
    if no_llm or not cfg.xai_api_key:
        if not no_llm:
            console.print("[yellow]No XAI_API_KEY — using heuristic analyzer only.[/yellow]")
        return HybridAnalyzer(llm=None)
    return HybridAnalyzer(llm=GrokAnalyzer(api_key=cfg.xai_api_key, model=cfg.xai_model))


async def _do_window_run(
    *,
    builder_name: str,
    track_count: int,
    dry_run: bool,
    public: bool,
    no_llm: bool,
    extra: dict | None = None,
) -> None:
    """Shared driver for daily/weekly/mood/viral."""
    cfg = Config.load()
    if cfg.missing:
        console.print(f"[red]Missing required env vars: {', '.join(cfg.missing)}[/red]")
        raise typer.Exit(2)
    log_activity("A", target=f"djx {builder_name}")
    store = TokenStore(cfg.tokens_path)
    cache = DiskCache(cfg.cache_dir)
    spotify = SpotifyClient(
        store, client_id=cfg.spotify_client_id, client_secret=cfg.spotify_client_secret
    )
    xc = XClient(store, cache, client_id=cfg.x_client_id, client_secret=cfg.x_client_secret)
    analyzer = _make_analyzer(cfg, no_llm)

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as p:
            t = p.add_task(f"{builder_name}: gathering signals…", total=None)
            me_x = await xc.me()
            user_id_x = me_x.get("id", "")
            top = await spotify.top_artists(limit=20)

            if builder_name == "daily":
                ranked, window = await build_daily_pulse(
                    spotify, xc, analyzer,
                    user_id=user_id_x, top_artists=top, track_count=track_count,
                )
                name = daily_name()
                description = daily_description(window, len(window.all_analyses))
            elif builder_name == "weekly":
                ranked, window = await build_weekly_resonance(
                    spotify, xc, analyzer,
                    user_id=user_id_x, top_artists=top, track_count=track_count,
                    scrape_artist_tweets=(extra or {}).get("scrape", True),
                )
                name = weekly_name()
                description = weekly_description(window, len(window.all_analyses))
            elif builder_name == "mood":
                hours = (extra or {}).get("hours", 24)
                ranked, window, mood = await build_mood_mirror(
                    spotify, xc, analyzer,
                    user_id=user_id_x, track_count=track_count, hours=hours,
                )
                name = mood_mirror_name(mood)
                description = (
                    f"Mirroring your dominant mood ({mood}) over the last {hours}h. "
                    f"Energy: {window.dominant_energy}."
                )
            elif builder_name == "viral":
                hours = (extra or {}).get("hours", 48)
                ranked, window = await build_viral_surge(
                    spotify, xc, analyzer,
                    user_id=user_id_x, track_count=track_count, hours=hours,
                )
                name = viral_surge_name()
                top_names = ", ".join(n for n, _ in window.viral_artists[:5])
                description = (
                    f"Viral Surge ({hours}h). Most-mentioned: {top_names or 'none yet'}."
                )
            else:
                raise typer.Exit(2)

            p.update(t, description=f"{builder_name}: ranked {len(ranked)} tracks")

            if dry_run:
                console.print(f"\n[bold]DRY RUN[/bold] — would create '{name}':")
                for s in ranked:
                    console.print(
                        f"  {s.score:>5.2f}  {s.candidate.artist_name} — {s.candidate.name}"
                    )
                console.print(f"\n[dim]{description}[/dim]")
            else:
                me_sp = await spotify.me()
                from djx.recommender.playlist import build_playlist as _bp
                result = await _bp(
                    spotify, me_sp["id"], ranked,
                    name=name, description=description, public=public,
                )
                if result.get("degraded"):
                    console.print(
                        "\n[yellow]Spotify refused to create the playlist (403).[/yellow]"
                    )
                    console.print(
                        "[yellow]Your dev-mode app must whitelist your account.[/yellow]"
                    )
                    console.print(
                        "Fix: developer.spotify.com/dashboard → your app → Settings → User Management → Add user"
                    )
                    console.print(
                        f"\nMeanwhile, {result['track_count']} track URIs were written to:\n  {result['uris_file']}"
                    )
                    console.print("\n[bold]Track list:[/bold]")
                    for t in result["tracks"]:
                        console.print(f"  {t['score']:>5.2f}  {t['artist']} — {t['name']}")
                else:
                    console.print(f"[green]Created:[/green] {result.get('url') or name}")
                    console.print(f"[green]Tracks added:[/green] {result['track_count']}")

        run_path = cfg.runs_dir / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{builder_name}.json"
        run_path.write_text(
            json.dumps({
                "builder": builder_name,
                "name": name,
                "description": description,
                "mood": window.dominant_mood,
                "energy": window.dominant_energy,
                "viral_artists": window.viral_artists[:10],
                "locations": window.locations[:5],
                "tracks": [
                    {"name": s.candidate.name, "artist": s.candidate.artist_name,
                     "score": s.score, "seed": s.candidate.seed_artist}
                    for s in ranked
                ],
            }, indent=2),
            encoding="utf-8",
        )
        console.print(f"Run summary: {run_path}")
    finally:
        await spotify.aclose()
        await xc.aclose()
        log_activity("Z", target=f"djx {builder_name}")


@app.command()
def daily(
    track_count: int = typer.Option(30, help="Tracks in the playlist"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    public: bool = typer.Option(False),
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Daily Pulse — last 24h of user signal + global pulse."""
    asyncio.run(_do_window_run(
        builder_name="daily", track_count=track_count,
        dry_run=dry_run, public=public, no_llm=no_llm,
    ))


@app.command()
def weekly(
    track_count: int = typer.Option(50, help="Tracks in the playlist"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    public: bool = typer.Option(False),
    no_llm: bool = typer.Option(False, "--no-llm"),
    no_scrape: bool = typer.Option(
        False, "--no-scrape", help="Skip per-artist tweet scraping (faster)"
    ),
) -> None:
    """Weekly Resonance — 7-day broader sweep with artist scraping."""
    asyncio.run(_do_window_run(
        builder_name="weekly", track_count=track_count,
        dry_run=dry_run, public=public, no_llm=no_llm,
        extra={"scrape": not no_scrape},
    ))


@app.command()
def mood(
    hours: int = typer.Option(24, help="Look-back window in hours"),
    track_count: int = typer.Option(25, help="Tracks in the playlist"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    public: bool = typer.Option(False),
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Mood Mirror — playlist that matches your dominant emotional tone."""
    asyncio.run(_do_window_run(
        builder_name="mood", track_count=track_count,
        dry_run=dry_run, public=public, no_llm=no_llm,
        extra={"hours": hours},
    ))


@app.command()
def viral(
    hours: int = typer.Option(48, help="Look-back window in hours"),
    track_count: int = typer.Option(25, help="Tracks in the playlist"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    public: bool = typer.Option(False),
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Viral Surge — heavily prioritize artists trending across your X feed."""
    asyncio.run(_do_window_run(
        builder_name="viral", track_count=track_count,
        dry_run=dry_run, public=public, no_llm=no_llm,
        extra={"hours": hours},
    ))


async def _run_async(
    max_artists: int, track_count: int, dry_run: bool, public: bool, no_llm: bool
) -> None:
    cfg = Config.load()
    if cfg.missing:
        console.print(f"[red]Missing required env vars: {', '.join(cfg.missing)}[/red]")
        console.print("Copy .env.example to .env and fill in your keys.")
        raise typer.Exit(2)

    log_activity("A", target="djx run")
    store = TokenStore(cfg.tokens_path)
    cache = DiskCache(cfg.cache_dir)

    spotify = SpotifyClient(
        store, client_id=cfg.spotify_client_id, client_secret=cfg.spotify_client_secret
    )
    xc = XClient(store, cache, client_id=cfg.x_client_id, client_secret=cfg.x_client_secret)

    if no_llm or not cfg.xai_api_key:
        analyzer = HybridAnalyzer(llm=None)
        if not no_llm:
            console.print("[yellow]No XAI_API_KEY — using heuristic analyzer only.[/yellow]")
    else:
        analyzer = HybridAnalyzer(llm=GrokAnalyzer(api_key=cfg.xai_api_key, model=cfg.xai_model))

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as p:
            t = p.add_task("Fetching Spotify top artists…", total=None)
            top = await spotify.top_artists(limit=max_artists)
            p.update(t, description=f"Got {len(top)} top artists")

            recently = []
            try:
                rp = await spotify.recently_played(limit=50)
                recently = [it["track"]["id"] for it in rp if it.get("track")]
            except Exception:
                pass

            artist_analyses: dict[str, list] = {}
            for artist in top:
                p.update(t, description=f"X scan: {artist['name']}")
                user = await xc.find_user_by_username(artist["name"].replace(" ", ""))
                if user is None:
                    results = await xc.search_user(artist["name"], max_results=1)
                    user = results[0] if results else None
                if not user or not user.get("id"):
                    continue
                tweets = await xc.user_tweets(user["id"], max_results=50)
                texts = [tw.get("text", "") for tw in tweets]
                artist_analyses[artist["name"]] = await analyzer.analyze_batch(texts)

            p.update(t, description="Fetching your liked tweets")
            user_likes_analyses = []
            try:
                me = await xc.me()
                if me.get("id"):
                    likes = await xc.liked_tweets(me["id"], max_results=50)
                    user_likes_analyses = await analyzer.analyze_batch(
                        [tw.get("text", "") for tw in likes]
                    )
            except Exception as e:
                console.print(f"[yellow]Skipping liked tweets: {e}[/yellow]")

            p.update(t, description="Building seed pool")
            pool = build_seeds(top, artist_analyses, user_likes_analyses)

            p.update(t, description="Expanding candidates via Spotify")
            candidates = await expand_candidates(spotify, pool)

            p.update(t, description="Ranking")
            ranked = Recommender().rank(
                candidates,
                pool,
                already_played_track_ids=set(recently),
                target_count=track_count,
            )

            p.update(t, description="Building playlist")
            me_spotify = await spotify.me()
            description = playlist_description(
                num_seeds=len(top),
                num_tweets=sum(len(v) for v in artist_analyses.values()) + len(user_likes_analyses),
                mood=pool.dominant_mood,
                energy=pool.dominant_energy,
            )
            result = await build_playlist(
                spotify,
                me_spotify["id"],
                ranked,
                name=playlist_name(dt.date.today()),
                description=description,
                public=public,
                dry_run=dry_run,
            )

        run_path = cfg.runs_dir / f"{dt.datetime.now():%Y%m%d_%H%M%S}.json"
        run_path.write_text(
            json.dumps(
                {
                    "result": result,
                    "mood": pool.dominant_mood,
                    "energy": pool.dominant_energy,
                    "seed_artists": [a["name"] for a in top],
                    "candidate_count": len(candidates),
                    "tracks": [
                        {"name": s.candidate.name, "artist": s.candidate.artist_name, "score": s.score}
                        for s in ranked
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        if dry_run:
            console.print(f"\n[bold]DRY RUN[/bold] — would create '{result['name']}':")
            for r in result["tracks"]:
                console.print(f"  {r['score']:>5.2f}  {r['artist']} — {r['name']}")
        elif result.get("degraded"):
            console.print(
                "\n[yellow]Spotify refused to create the playlist (403).[/yellow]"
            )
            console.print(
                "Fix: developer.spotify.com/dashboard → your app → Settings → User Management → Add user"
            )
            console.print(
                f"\n{result['track_count']} URIs written to: {result['uris_file']}"
            )
            console.print("\n[bold]Track list:[/bold]")
            for t in result["tracks"]:
                console.print(f"  {t['score']:>5.2f}  {t['artist']} — {t['name']}")
        else:
            console.print(f"[green]Created:[/green] {result.get('url') or result['name']}")
            console.print(f"[green]Tracks added:[/green] {result['track_count']}")
        console.print(f"Run summary: {run_path}")
    finally:
        await spotify.aclose()
        await xc.aclose()
        log_activity("Z", target="djx run")


# ============================================================================
# Podcast Pulse commands
# ============================================================================

from djx.podcasts import (  # noqa: E402
    AffinityStore,
    PodcastRunResult,
    extract_podcast_signals,
    make_grok_enricher,
    normalize_to_100,
    process_window,
)


def _affinity_path(cfg: Config):
    return cfg.tokens_path.parent / "affinity.json"


async def _do_podcast_run(window_hours: int, no_llm: bool, resolve_max: int) -> PodcastRunResult:
    cfg = Config.load()
    if cfg.missing:
        console.print(f"[red]Missing required env vars: {', '.join(cfg.missing)}[/red]")
        raise typer.Exit(2)
    log_activity("A", target=f"djx podcasts run {window_hours}h")
    store = TokenStore(cfg.tokens_path)
    cache = DiskCache(cfg.cache_dir)
    spotify = SpotifyClient(
        store, client_id=cfg.spotify_client_id, client_secret=cfg.spotify_client_secret
    )
    xc = XClient(store, cache, client_id=cfg.x_client_id, client_secret=cfg.x_client_secret)
    affinity = AffinityStore.load(_affinity_path(cfg))

    enricher = None
    if not no_llm and cfg.xai_api_key:
        enricher = make_grok_enricher(api_key=cfg.xai_api_key, model=cfg.xai_model)

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as p:
            t = p.add_task(f"podcasts: scanning last {window_hours}h…", total=None)
            me_x = await xc.me()
            user_id_x = me_x.get("id", "")
            result = await process_window(
                xc=xc, spotify=spotify, affinity=affinity,
                user_id=user_id_x, window_hours=window_hours,
                enricher=enricher, resolve_max=resolve_max,
            )
            p.update(t, description=f"podcasts: {len(result.matches)} matches")
        return result
    finally:
        await spotify.aclose()
        await xc.aclose()
        log_activity("Z", target=f"djx podcasts run {window_hours}h")


def _print_matches(matches) -> None:
    if not matches:
        console.print("[yellow]No clip-to-episode matches in this window.[/yellow]")
        return
    console.print("\n[bold]Clip → full episode matches[/bold]")
    for m in matches:
        console.print(
            f"\n  [cyan]{m.show_name}[/cyan] — {m.episode_name}\n"
            f"  strength: {m.match_strength:.2f}\n"
            f"  {m.explanation}\n"
            f"  [link]{m.spotify_url}[/link]"
        )


def _print_affinity(affinity: AffinityStore) -> None:
    for kind, label in [("host", "Top hosts"), ("show", "Top shows"), ("topic", "Top topics")]:
        rows = affinity.top(kind, n=10)
        if not rows:
            continue
        normed = normalize_to_100(rows)
        table = Table(title=label, show_lines=False)
        table.add_column("Name")
        table.add_column("Score (0-100)", justify="right")
        table.add_column("Likes", justify="right")
        for name, score, n in normed:
            table.add_row(name, str(score), str(n))
        console.print(table)


@podcasts_app.command("resolve")
def podcasts_resolve(
    hours: int = typer.Option(24, help="Look-back window in hours"),
    resolve_max: int = typer.Option(10, help="Max episodes to resolve"),
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Scan recent likes/timeline, resolve clips to full Spotify episodes,
    and update the affinity store."""
    result = asyncio.run(_do_podcast_run(hours, no_llm, resolve_max))
    console.print(
        f"\nProcessed {result.raw_tweets_processed} tweets, "
        f"{result.podcast_clip_count} podcast clips detected, "
        f"{result.new_events} affinity events recorded."
    )
    _print_matches(result.matches)


@podcasts_app.command("daily")
def podcasts_daily(
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Daily Podcast Pulse — last 24h."""
    result = asyncio.run(_do_podcast_run(24, no_llm, resolve_max=15))
    console.print(
        f"\n[bold]Daily Podcast Pulse[/bold] — {result.podcast_clip_count} clips → "
        f"{len(result.matches)} episodes"
    )
    _print_matches(result.matches)


@podcasts_app.command("weekly")
def podcasts_weekly(
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Weekly Podcast Resonance — last 7 days."""
    result = asyncio.run(_do_podcast_run(24 * 7, no_llm, resolve_max=25))
    console.print(
        f"\n[bold]Weekly Podcast Resonance[/bold] — {result.podcast_clip_count} clips → "
        f"{len(result.matches)} episodes"
    )
    _print_matches(result.matches)


@podcasts_app.command("affinity")
def podcasts_affinity() -> None:
    """Show your current host/show/topic affinity report."""
    cfg = Config.load()
    affinity = AffinityStore.load(_affinity_path(cfg))
    if not affinity.events:
        console.print(
            "[yellow]No affinity data yet. Run `djx podcasts resolve` first to seed it.[/yellow]"
        )
        return
    _print_affinity(affinity)


@podcasts_app.command("explain")
def podcasts_explain(
    text: str = typer.Argument(..., help="The tweet text to analyze"),
) -> None:
    """Run the podcast signal extractor on one tweet (debug helper)."""
    sig = asyncio.run(extract_podcast_signals(text))
    console.print(sig.model_dump())
