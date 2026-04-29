from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from djx.analyzer.schema import TweetAnalysis


@dataclass
class SeedPool:
    """Aggregated, ranked signals to feed the candidate generator."""

    artist_weights: Counter = field(default_factory=Counter)  # name -> weight
    track_hints: Counter = field(default_factory=Counter)     # title -> weight
    streaming_links: list[str] = field(default_factory=list)
    moods: Counter = field(default_factory=Counter)
    energies: Counter = field(default_factory=Counter)

    @property
    def dominant_mood(self) -> str:
        return self.moods.most_common(1)[0][0] if self.moods else "neutral"

    @property
    def dominant_energy(self) -> str:
        return self.energies.most_common(1)[0][0] if self.energies else "medium"


def build_seeds(
    top_artists: list[dict],
    artist_analyses: dict[str, list[TweetAnalysis]],
    user_likes_analyses: list[TweetAnalysis],
) -> SeedPool:
    """Combine all signals into a weighted seed pool.

    Weights:
      - top artist (always present)            +5
      - artist mentioned in their own tweets   +2 per mention (capped 6)
      - artist mentioned in user's liked tweets+3 per mention (capped 9)
      - artist's tweet announces a release     +5
      - artist recommends another artist       +2 to that recommendation
    """
    pool = SeedPool()

    for a in top_artists:
        pool.artist_weights[a["name"]] += 5

    for artist_name, analyses in artist_analyses.items():
        bump = 0
        for an in analyses:
            if an.is_new_release:
                bump += 5
            for t in an.tracks:
                pool.track_hints[t] += 2
            for rec in an.recommended_artists:
                pool.artist_weights[rec] += 2
            pool.streaming_links.extend(an.streaming_links)
            pool.moods[an.mood] += 1
            pool.energies[an.energy_level] += 1
        pool.artist_weights[artist_name] += min(bump, 6)

    for an in user_likes_analyses:
        for name in an.artists:
            pool.artist_weights[name] += min(3, 3)
        for rec in an.recommended_artists:
            pool.artist_weights[rec] += 2
        for t in an.tracks:
            pool.track_hints[t] += 3
        pool.streaming_links.extend(an.streaming_links)
        pool.moods[an.mood] += 2
        pool.energies[an.energy_level] += 2

    return pool
