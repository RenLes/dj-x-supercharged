"""High-level orchestrator: tweets → podcast signals → affinity update → episode matches."""

from __future__ import annotations

from dataclasses import dataclass

from djx.clients.spotify import SpotifyClient
from djx.clients.x import XClient
from djx.insights.trends import summarize_trends
from djx.insights.window import within_window
from djx.podcasts.affinity import AffinityStore
from djx.podcasts.foryou import topics_from_personalized_trends, topics_from_tweet_corpus
from djx.podcasts.resolver import EpisodeMatch, recommend_by_topics, resolve_episode
from djx.podcasts.signals import LLMEnricher, PodcastSignal, extract_podcast_signals


@dataclass
class PodcastRunResult:
    matches: list[EpisodeMatch]
    signals: list[PodcastSignal]
    raw_tweets_processed: int
    podcast_clip_count: int
    new_events: int
    foryou_topics: list[str]


# Weights when a clip-like tweet is liked.
LIKE_HOST_WEIGHT = 1.0
LIKE_SHOW_WEIGHT = 1.0
LIKE_TOPIC_WEIGHT = 0.5
RELEASE_BONUS = 1.0


async def process_window(
    *,
    xc: XClient,
    spotify: SpotifyClient,
    affinity: AffinityStore,
    user_id: str,
    window_hours: int,
    likes_max: int = 100,
    timeline_max: int = 100,
    include_timeline: bool = True,
    enricher: LLMEnricher | None = None,
    resolve_max: int = 10,
    min_recommendations: int = 5,
) -> PodcastRunResult:
    """Run the full podcast pipeline for a time window.

    Steps:
      1. Fetch likes (and optionally home timeline) for the window.
      2. Extract podcast signals from each tweet.
      3. Update the affinity store for hosts/shows/topics observed.
      4. For the highest-confidence clip signals, resolve full episodes on Spotify.
    """
    raw_likes = await xc.liked_tweets(user_id, max_results=likes_max)
    raw_likes = [t for t in raw_likes if within_window(t, hours=window_hours)]

    raw_timeline: list[dict] = []
    if include_timeline:
        from djx.insights.window import iso_window_start
        start = iso_window_start(hours=window_hours)
        raw_timeline = await xc.home_timeline(user_id, max_results=timeline_max, start_time=start)

    # X's "For You" signal — the closest the v2 API exposes to the algorithm.
    # Two sources, blended:
    #   1. /users/personalized_trends — direct For You signal (paywalled on some tiers)
    #   2. Keyword analysis of liked-tweet text — works on every tier, similar fidelity
    raw_trends = await xc.personalized_trends()
    summarize_trends(raw_trends)  # silently runs validation (signal categorisation)
    trend_topics = topics_from_personalized_trends(raw_trends) if raw_trends else []
    corpus_topics = topics_from_tweet_corpus(raw_likes + raw_timeline)
    # Merge: trends first (stronger signal when present), corpus topics fill in.
    foryou_topics: list[str] = []
    for t in trend_topics + corpus_topics:
        if t not in foryou_topics:
            foryou_topics.append(t)

    candidates: list[tuple[dict, float]] = [(t, 1.0) for t in raw_likes]
    candidates += [(t, 0.5) for t in raw_timeline]  # timeline contributes half

    signals: list[PodcastSignal] = []
    new_events = 0
    for tweet, source_weight in candidates:
        text = tweet.get("text", "") or ""
        if not text:
            continue
        sig = await extract_podcast_signals(text, llm_enricher=enricher)
        signals.append(sig)
        if sig.is_podcast_clip:
            new_events += _record_signal_to_affinity(affinity, sig, source_weight)

    affinity.deduplicate_by_tweet_window(hours=1)
    affinity.save()

    # Pick the highest-confidence clip signals for episode resolution
    clipworthy = [s for s in signals if s.is_podcast_clip and s.confidence >= 0.4]
    clipworthy.sort(key=lambda s: s.confidence, reverse=True)

    matches: list[EpisodeMatch] = []
    seen_episode_ids: set[str] = set()
    for s in clipworthy[:resolve_max]:
        try:
            m = await resolve_episode(spotify, s)
        except Exception:
            continue
        if m and m.episode_id not in seen_episode_ids:
            seen_episode_ids.add(m.episode_id)
            matches.append(m)

    # Topic-based fallback when clip resolution under-delivers.
    # Priority order: For You trends (X's algorithmic signal) > liked-tweet topics > affinity > defaults.
    if len(matches) < min_recommendations:
        topics: list[str] = list(foryou_topics)
        for sig in signals:
            for topic in sig.topics:
                if topic not in topics:
                    topics.append(topic)
        for name, _, _ in affinity.top("topic", n=10):
            if name not in topics:
                topics.append(name)
        if not topics:
            topics = ["interview", "comedy", "ai", "self-improvement", "business"]

        needed = min_recommendations - len(matches)
        try:
            extra = await recommend_by_topics(spotify, topics, needed=needed)
        except Exception:
            extra = []
        for m in extra:
            if m.episode_id not in seen_episode_ids:
                seen_episode_ids.add(m.episode_id)
                matches.append(m)

    return PodcastRunResult(
        matches=matches,
        signals=signals,
        raw_tweets_processed=len(candidates),
        podcast_clip_count=sum(1 for s in signals if s.is_podcast_clip),
        new_events=new_events,
        foryou_topics=foryou_topics,
    )


def _record_signal_to_affinity(
    affinity: AffinityStore, sig: PodcastSignal, source_weight: float
) -> int:
    """Append events to the affinity store. Returns number of events appended."""
    n = 0
    if sig.host:
        affinity.record_signal("host", sig.host, weight=LIKE_HOST_WEIGHT * source_weight)
        n += 1
    if sig.show and sig.show != sig.host:
        affinity.record_signal("show", sig.show, weight=LIKE_SHOW_WEIGHT * source_weight)
        n += 1
    for topic in sig.topics:
        affinity.record_signal("topic", topic, weight=LIKE_TOPIC_WEIGHT * source_weight)
        n += 1
    return n
