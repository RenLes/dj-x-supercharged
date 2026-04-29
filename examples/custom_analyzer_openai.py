"""Plug OpenAI in as the LLM analyzer.

    pip install openai

Set OPENAI_API_KEY in your env, then:

    from djx import HybridAnalyzer
    analyzer = HybridAnalyzer(llm=OpenAIAnalyzer())
"""

from __future__ import annotations

import json
import os

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.schema import TweetAnalysis

PROMPT = (
    "Analyze this tweet. Return ONLY JSON with keys: artists, tracks, is_new_release, "
    "release_type, streaming_links, mood, energy_level, recommended_artists, hashtags, confidence. "
    "Tweet: {tweet}"
)


class OpenAIAnalyzer(BaseAnalyzer):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as e:
            raise ImportError("Install with: pip install openai") from e
        self._client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        try:
            r = await self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": PROMPT.format(tweet=tweet_text)}],
            )
            data = json.loads(r.choices[0].message.content or "{}")
            return TweetAnalysis.model_validate(data)
        except Exception:
            return TweetAnalysis(confidence=0.4)
