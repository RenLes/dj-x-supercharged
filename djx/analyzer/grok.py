from __future__ import annotations

import json

import httpx

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.schema import TweetAnalysis

XAI_ENDPOINT = "https://api.x.ai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You analyze tweets for music signals. Return ONLY a JSON object that matches the "
    "provided schema exactly. No prose, no markdown."
)

USER_TEMPLATE = (
    "Analyze this tweet and return JSON with these fields:\n"
    "  artists (string[]): artist names mentioned\n"
    "  tracks (string[]): track titles mentioned (quoted strings or context-clear titles)\n"
    "  is_new_release (bool): does it announce a new release?\n"
    '  release_type ("single" | "album" | "ep" | null)\n'
    "  streaming_links (string[]): Spotify/Apple/Tidal/YouTube/SoundCloud URLs\n"
    '  mood ("hype"|"chill"|"dark"|"energetic"|"romantic"|"aggressive"|"neutral")\n'
    '  energy_level ("high"|"medium"|"low")\n'
    "  recommended_artists (string[]): artists you'd recommend if a listener liked this tweet\n"
    "  hashtags (string[]): hashtags without the #\n"
    "  confidence (number 0.0–1.0)\n\n"
    "Tweet: {tweet}"
)


class GrokAnalyzer(BaseAnalyzer):
    """xAI Grok-backed analyzer using structured outputs."""

    def __init__(
        self,
        api_key: str,
        model: str = "grok-4-fast",
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("GrokAnalyzer requires an xAI API key.")
        self.api_key = api_key
        self.model = model
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(tweet=tweet_text)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            r = await self._client.post(XAI_ENDPOINT, headers=headers, json=body)
            r.raise_for_status()
            payload = r.json()
            raw = payload["choices"][0]["message"]["content"]
            data = json.loads(raw)
            return TweetAnalysis.model_validate(data)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValueError):
            return TweetAnalysis(confidence=0.4)
