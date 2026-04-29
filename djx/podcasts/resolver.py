"""Resolve a podcast clip signal to a full Spotify episode."""

from __future__ import annotations

from dataclasses import dataclass

from djx.clients.spotify import SpotifyClient
from djx.podcasts.signals import PodcastSignal


@dataclass
class EpisodeMatch:
    """A matched (or guessed) Spotify episode for a clip signal."""

    episode_id: str
    episode_name: str
    show_name: str
    spotify_url: str
    match_strength: float          # 0.0 – 1.0
    explanation: str               # human-readable "because you liked..."
    raw_signal: PodcastSignal


def _build_query(signal: PodcastSignal) -> str | None:
    """Compose a Spotify search query from a signal. Returns None if too thin."""
    parts: list[str] = []
    if signal.show:
        parts.append(signal.show)
    if signal.host and signal.host != signal.show:
        parts.append(signal.host)
    if signal.guest:
        parts.append(signal.guest)
    if signal.topic_hint:
        parts.append(signal.topic_hint[:60])
    if not parts and signal.topics:
        parts.append(signal.topics[0])
    if not parts:
        return None
    return " ".join(parts)[:200]


def _strength(signal: PodcastSignal, episode: dict, show_match: bool) -> float:
    """Heuristic strength for an episode match."""
    score = 0.4 if show_match else 0.2
    name = (episode.get("name") or "").lower()
    if signal.guest and signal.guest.lower() in name:
        score += 0.3
    if signal.topic_hint and signal.topic_hint.lower() in name:
        score += 0.2
    if signal.host and signal.host.lower() in name:
        score += 0.05
    return min(round(score, 2), 0.95)


async def resolve_episode(
    spotify: SpotifyClient, signal: PodcastSignal
) -> EpisodeMatch | None:
    """Best-effort match: signal → Spotify episode."""
    if not signal.is_podcast_clip:
        return None
    query = _build_query(signal)
    if not query:
        return None

    # Strategy 1: episode search using the full composed query
    episodes = await spotify.search_episodes(query, limit=5)
    if episodes:
        best = episodes[0]
        return _episode_to_match(best, signal, show_match=True, query=query)

    # Strategy 2: fall back to show search → most recent episode
    show_query = signal.show or signal.host
    if show_query:
        shows = await spotify.search_shows(show_query, limit=1)
        if shows:
            show = shows[0]
            try:
                eps = await spotify.show_episodes(show["id"], limit=5)
            except Exception:
                eps = []
            if eps:
                best = eps[0]
                return _episode_to_match(best, signal, show_match=False, query=query)
    return None


async def recommend_by_topics(
    spotify: SpotifyClient,
    topics: list[str],
    *,
    needed: int,
    explanation_prefix: str = "Because your X 'For You' shows interest in",
) -> list[EpisodeMatch]:
    """Topic-driven fallback that rotates across topics for diversity.

    Strategy:
      1. For each topic, fetch the top show (1 per topic).
      2. Pull the most recent episode of each show.
      3. Continue across topics so the recommendations span your interests
         instead of returning N episodes from the same single-topic search.
    """
    out: list[EpisodeMatch] = []
    seen_episode_ids: set[str] = set()
    seen_show_ids: set[str] = set()

    import re as _re

    # Pass 1: one show per topic — maximum diversity
    for topic in topics:
        if len(out) >= needed:
            break
        try:
            shows = await spotify.search_shows(topic, limit=2)
        except Exception:
            continue
        if not shows:
            continue
        # Word-boundary regex: avoids "ai" matching inside "AIN'T" / "main".
        topic_tokens = [t for t in topic.split() if t]
        token_res = [
            _re.compile(rf"\b{_re.escape(t)}\b", _re.IGNORECASE) for t in topic_tokens
        ]
        for show in shows:
            sid = show.get("id", "")
            if not sid or sid in seen_show_ids:
                continue
            show_name = show.get("name") or ""
            show_desc = (show.get("description") or "")[:300]
            haystack = f"{show_name} {show_desc}"
            if token_res and not any(p.search(haystack) for p in token_res) and len(shows) > 1:
                # name/description doesn't contain the topic; skip unless it's our only choice
                continue
            seen_show_ids.add(sid)
            try:
                eps = await spotify.show_episodes(sid, limit=2)
            except Exception:
                continue
            for ep in eps[:1]:
                if ep is None:
                    continue
                ep_id = ep.get("id", "")
                if not ep_id or ep_id in seen_episode_ids:
                    continue
                seen_episode_ids.add(ep_id)
                out.append(_build_topic_match(ep, show, topic, explanation_prefix))
                break  # only the most recent episode for diversity
            break  # only first matching show per topic

    # Pass 2: backfill from the strongest topic if we still need more
    if len(out) < needed and topics:
        for topic in topics[:2]:
            if len(out) >= needed:
                break
            try:
                shows = await spotify.search_shows(topic, limit=4)
            except Exception:
                continue
            for show in shows:
                if len(out) >= needed:
                    break
                sid = show.get("id", "")
                if not sid or sid in seen_show_ids:
                    continue
                seen_show_ids.add(sid)
                try:
                    eps = await spotify.show_episodes(sid, limit=2)
                except Exception:
                    continue
                for ep in eps[:1]:
                    if ep is None:
                        continue
                    ep_id = ep.get("id", "")
                    if not ep_id or ep_id in seen_episode_ids:
                        continue
                    seen_episode_ids.add(ep_id)
                    out.append(_build_topic_match(ep, show, topic, explanation_prefix))
                    break
    return out


def _build_topic_match(
    ep: dict, show: dict, topic: str, explanation_prefix: str
) -> EpisodeMatch:
    ep_id = ep.get("id", "")
    fake_signal = PodcastSignal(
        is_podcast_clip=False,
        topics=[topic],
        confidence=0.3,
    )
    return EpisodeMatch(
        episode_id=ep_id,
        episode_name=ep.get("name", "Unknown episode"),
        show_name=show.get("name", "Unknown Show"),
        spotify_url=(ep.get("external_urls", {}) or {}).get(
            "spotify", f"https://open.spotify.com/episode/{ep_id}"
        ),
        match_strength=0.3,
        explanation=f"{explanation_prefix} {topic}.",
        raw_signal=fake_signal,
    )


def _episode_to_match(
    ep: dict, signal: PodcastSignal, *, show_match: bool, query: str
) -> EpisodeMatch:
    show_name = (ep.get("show", {}) or {}).get("name", signal.show or "Unknown Show")
    if not show_name and signal.show:
        show_name = signal.show
    explanation_parts = []
    if signal.host:
        explanation_parts.append(f"you've engaged with {signal.host} clips")
    elif signal.show:
        explanation_parts.append(f"you've liked clips from {signal.show}")
    if signal.guest:
        explanation_parts.append(f"this episode features {signal.guest}")
    if signal.topic_hint:
        explanation_parts.append(f"the clip mentioned “{signal.topic_hint}”")
    explanation = (
        "; ".join(explanation_parts) if explanation_parts else f"matched query: {query}"
    )
    return EpisodeMatch(
        episode_id=ep.get("id", ""),
        episode_name=ep.get("name", "Unknown episode"),
        show_name=show_name or "Unknown Show",
        spotify_url=(ep.get("external_urls", {}) or {}).get(
            "spotify", f"https://open.spotify.com/episode/{ep.get('id', '')}"
        ),
        match_strength=_strength(signal, ep, show_match),
        explanation=f"Because {explanation}.",
        raw_signal=signal,
    )
