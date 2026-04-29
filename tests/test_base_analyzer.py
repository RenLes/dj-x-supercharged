"""Contract tests every BaseAnalyzer subclass should satisfy.

Forkers shipping a custom analyzer should import `analyzer_contract` from this
module (or copy the helper) and run it against their subclass.
"""

from __future__ import annotations

import asyncio

import pytest

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.heuristic import HeuristicAnalyzer
from djx.analyzer.hybrid import HybridAnalyzer
from djx.analyzer.schema import TweetAnalysis


async def analyzer_contract(analyzer: BaseAnalyzer) -> None:
    """Assert that `analyzer` honors the BaseAnalyzer contract."""
    out = await analyzer.analyze("New single 'Storm' out now: https://open.spotify.com/track/x")
    assert isinstance(out, TweetAnalysis)
    assert 0.0 <= out.confidence <= 1.0

    batch = await analyzer.analyze_batch(["a", "b", "c"])
    assert len(batch) == 3
    assert all(isinstance(b, TweetAnalysis) for b in batch)


def test_heuristic_passes_contract():
    asyncio.run(analyzer_contract(HeuristicAnalyzer()))


def test_hybrid_without_llm_passes_contract():
    asyncio.run(analyzer_contract(HybridAnalyzer(llm=None)))


class _BrokenAnalyzer(BaseAnalyzer):
    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        raise RuntimeError("intentional")


def test_batch_swallows_per_item_errors():
    res = asyncio.run(_BrokenAnalyzer().analyze_batch(["a", "b"]))
    assert len(res) == 2
    assert all(r.confidence == 0.0 for r in res)


def test_subclass_must_implement_analyze():
    with pytest.raises(TypeError):
        BaseAnalyzer()  # type: ignore[abstract]
