from __future__ import annotations

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.heuristic import HeuristicAnalyzer
from djx.analyzer.schema import TweetAnalysis

LLM_ESCALATION_THRESHOLD = 0.6


class HybridAnalyzer(BaseAnalyzer):
    """Heuristic-first; escalates to an LLM analyzer only when confidence is low.

    Merges results so heuristic-derived hard facts (links, hashtags, release_type)
    survive even if the LLM disagrees.
    """

    def __init__(self, llm: BaseAnalyzer | None, *, threshold: float = LLM_ESCALATION_THRESHOLD):
        self.llm = llm
        self.heuristic = HeuristicAnalyzer()
        self.threshold = threshold

    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        h = self.heuristic.analyze_sync(tweet_text)
        if self.llm is None or h.confidence >= self.threshold:
            return h
        llm_out = await self.llm.analyze(tweet_text)
        return _merge(h, llm_out)


def _merge(h: TweetAnalysis, m: TweetAnalysis) -> TweetAnalysis:
    artists = _union(h.artists, m.artists)
    tracks = _union(h.tracks, m.tracks)
    streaming = _union(h.streaming_links, m.streaming_links)
    hashtags = _union(h.hashtags, m.hashtags)
    return TweetAnalysis(
        artists=artists,
        tracks=tracks,
        is_new_release=h.is_new_release or m.is_new_release,
        release_type=h.release_type or m.release_type,
        streaming_links=streaming,
        mood=m.mood if m.confidence > 0.4 else h.mood,
        energy_level=m.energy_level if m.confidence > 0.4 else h.energy_level,
        recommended_artists=m.recommended_artists,
        hashtags=hashtags,
        confidence=round(max(h.confidence, m.confidence), 2),
    )


def _union(a: list[str], b: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in [*a, *b]:
        s = (v or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out
