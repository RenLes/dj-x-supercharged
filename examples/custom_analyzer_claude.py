"""Plug Anthropic Claude in as the LLM analyzer.

    pip install anthropic

Set ANTHROPIC_API_KEY in your env, then:

    from djx import HybridAnalyzer
    analyzer = HybridAnalyzer(llm=ClaudeAnalyzer())
"""

from __future__ import annotations

import json
import os

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.schema import TweetAnalysis

PROMPT = (
    "Analyze this tweet for music signals. Return ONLY a JSON object with keys: "
    "artists, tracks, is_new_release, release_type (single|album|ep|null), "
    "streaming_links, mood (hype|chill|dark|energetic|romantic|aggressive|neutral), "
    "energy_level (high|medium|low), recommended_artists, hashtags, "
    "confidence (0..1). Tweet: {tweet}"
)


class ClaudeAnalyzer(BaseAnalyzer):
    def __init__(self, model: str = "claude-haiku-4-5", api_key: str | None = None):
        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except ImportError as e:
            raise ImportError("Install with: pip install anthropic") from e
        self._client = AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        try:
            msg = await self._client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": PROMPT.format(tweet=tweet_text)}],
            )
            text = "".join(b.text for b in msg.content if b.type == "text")
            data = json.loads(text)
            return TweetAnalysis.model_validate(data)
        except Exception:
            return TweetAnalysis(confidence=0.4)
