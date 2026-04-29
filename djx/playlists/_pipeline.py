"""Shared async helper used by daily/weekly/mood/viral pipeline builders."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.schema import TweetAnalysis
from djx.clients.x import XClient
from djx.insights.location import detect_locations, woeid_for_country
from djx.insights.trends import TrendInsight, summarize_trends
from djx.insights.virality import detect_viral_artists, filter_via_spotify
from djx.insights.window import within_window


@dataclass
class TweetWindow:
    """Aggregated, analyzed tweet data for a time window."""

    likes: list[TweetAnalysis]
    timeline: list[TweetAnalysis]
    raw_likes: list[dict]
    raw_timeline: list[dict]
    trends: TrendInsight
    locations: list[tuple[str, int]]
    woeids: list[int]
    viral_artists: list[tuple[str, int]]
    dominant_mood: str
    dominant_energy: str

    @property
    def all_analyses(self) -> list[TweetAnalysis]:
        return [*self.likes, *self.timeline]


async def gather_window(
    xc: XClient,
    analyzer: BaseAnalyzer,
    *,
    user_id: str,
    start_time: str,
    window_hours: int,
    include_timeline: bool = True,
    include_trends: bool = True,
    likes_max: int = 100,
    timeline_max: int = 100,
    spotify_for_virality_check=None,  # SpotifyClient, optional cross-check
) -> TweetWindow:
    """Fetch likes + timeline + trends for a window, analyze, and aggregate.

    `liked_tweets` doesn't accept start_time on the X side, so we fetch the most
    recent likes and filter to the requested window in memory.
    """

    all_likes = await xc.liked_tweets(user_id, max_results=likes_max)
    raw_likes = [t for t in all_likes if within_window(t, hours=window_hours)]

    raw_timeline: list[dict] = []
    if include_timeline:
        raw_timeline = await xc.home_timeline(
            user_id, max_results=timeline_max, start_time=start_time
        )

    likes = await analyzer.analyze_batch([t.get("text", "") for t in raw_likes])
    timeline = await analyzer.analyze_batch([t.get("text", "") for t in raw_timeline])

    trends_data: list[dict] = []
    if include_trends:
        trends_data = await xc.personalized_trends()
    trends = summarize_trends(trends_data)

    location_corpus = [t.get("text", "") for t in raw_likes + raw_timeline] + [
        t.get("trend_name", "") for t in trends_data
    ]
    locations = detect_locations(location_corpus)
    woeids = [w for k, _ in locations[:3] if (w := woeid_for_country(k)) is not None]

    viral = detect_viral_artists([*likes, *timeline], min_mentions=2)
    if spotify_for_virality_check is not None and viral:
        viral = await filter_via_spotify(viral, spotify_for_virality_check)

    moods: Counter[str] = Counter()
    energies: Counter[str] = Counter()
    for a in [*likes, *timeline]:
        moods[a.mood] += 1
        energies[a.energy_level] += 1

    return TweetWindow(
        likes=likes,
        timeline=timeline,
        raw_likes=raw_likes,
        raw_timeline=raw_timeline,
        trends=trends,
        locations=locations,
        woeids=woeids,
        viral_artists=viral,
        dominant_mood=moods.most_common(1)[0][0] if moods else "neutral",
        dominant_energy=energies.most_common(1)[0][0] if energies else "medium",
    )
