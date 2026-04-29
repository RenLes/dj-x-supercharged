from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from djx.analyzer.schema import TweetAnalysis


class BaseAnalyzer(ABC):
    """Public extension point. Subclass to plug in any LLM (Claude, OpenAI, local)."""

    @abstractmethod
    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        """Return a TweetAnalysis for a single tweet."""

    async def analyze_batch(self, tweets: Iterable[str]) -> list[TweetAnalysis]:
        """Default sequential implementation; override for batched API calls."""
        results: list[TweetAnalysis] = []
        for t in tweets:
            try:
                results.append(await self.analyze(t))
            except Exception:
                results.append(TweetAnalysis(confidence=0.0))
        return results
