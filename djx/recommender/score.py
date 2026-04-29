from __future__ import annotations

import hashlib
from dataclasses import dataclass

from djx.recommender.candidates import TrackCandidate
from djx.recommender.seeds import SeedPool


@dataclass
class ScoredTrack:
    candidate: TrackCandidate
    score: float
    reasons: list[str]


# Source-quality multipliers — keeps similar-weighted candidates from collapsing
# to the same score when popularity is unavailable.
SOURCE_QUALITY: dict[str, float] = {
    "user_top": 0.20,         # /me/top/tracks — already personalized, modest bonus
    "tweet_hint": 0.15,       # quoted track from a tweet — noisy, lower bonus
    "global_viral": 0.10,
    "global_top": 0.05,
}


class Recommender:
    """Pure ranking layer. Stateless — testable without network."""

    def __init__(self, *, popularity_weight: float = 0.3, novelty_weight: float = 0.4):
        self.popularity_weight = popularity_weight
        self.novelty_weight = novelty_weight

    def rank(
        self,
        candidates: list[TrackCandidate],
        pool: SeedPool,
        *,
        already_played_track_ids: set[str] | None = None,
        target_count: int = 30,
    ) -> list[ScoredTrack]:
        already = already_played_track_ids or set()
        scored: list[ScoredTrack] = []
        seen_artists: dict[str, int] = {}

        for c in candidates:
            reasons: list[str] = []
            score = float(c.seed_weight)
            reasons.append(f"seed_weight={c.seed_weight}")

            score += self.popularity_weight * (c.popularity / 100.0)
            if c.popularity:
                reasons.append(f"pop={c.popularity}")

            # Source-quality bonus: prefers user_top > tweet_hint > viral > top
            for prefix, bonus in SOURCE_QUALITY.items():
                if c.seed_artist == prefix or c.seed_artist.startswith(f"{prefix}:"):
                    score += bonus
                    reasons.append(f"src:{prefix}(+{bonus})")
                    break

            if c.track_id in already:
                score -= 5.0
                reasons.append("recently_played(-5)")
            else:
                score += self.novelty_weight
                reasons.append(f"novelty(+{self.novelty_weight})")

            # Deterministic jitter: hash-based, stable across runs but breaks ties.
            jitter = (
                int(hashlib.sha256(c.track_id.encode()).hexdigest()[:6], 16) % 100
            ) / 1000.0
            score += jitter

            scored.append(ScoredTrack(candidate=c, score=round(score, 3), reasons=reasons))

        scored.sort(key=lambda s: s.score, reverse=True)

        # Diversify: at most 2 tracks per seed artist in top output
        out: list[ScoredTrack] = []
        for s in scored:
            if seen_artists.get(s.candidate.artist_name, 0) >= 2:
                continue
            out.append(s)
            seen_artists[s.candidate.artist_name] = seen_artists.get(s.candidate.artist_name, 0) + 1
            if len(out) >= target_count:
                break
        return out
