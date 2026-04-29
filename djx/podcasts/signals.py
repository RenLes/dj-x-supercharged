"""Extract podcast-related signals from a tweet.

Hybrid approach:
  1. Heuristic regex pass — fast, deterministic, offline
  2. Optional LLM (any BaseAnalyzer-style callable) for the non-obvious cases

Output schema is a Pydantic model so downstream code is type-safe.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, Field, field_validator

from djx.podcasts.known_hosts import HostEntry, detect_topics, find_host

CLIP_KEYWORDS_RE = re.compile(
    r"\b("
    r"clip|moment|highlight|excerpt|cut|snippet|"
    r"podcast|episode|ep\s*\d+|interview|"
    r"on\s+the\s+(?:show|podcast|pod)|guest|"
    r"timestamp|@\d+:\d+|\d+:\d+:\d+"
    r")\b",
    re.IGNORECASE,
)
SPOTIFY_PODCAST_HOST = re.compile(r"open\.spotify\.com/(episode|show)/([A-Za-z0-9]+)", re.IGNORECASE)
APPLE_PODCAST_HOST = re.compile(r"podcasts\.apple\.com/", re.IGNORECASE)
YOUTUBE_HOST = re.compile(r"(youtube\.com/watch|youtu\.be/)", re.IGNORECASE)

# "Joe Rogan with Elon Musk" / "JRE w/ Theo Von" — extract host + guest pair.
HOST_X_GUEST_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:w/?|with|and|x)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
)
QUOTED_TOPIC_RE = re.compile(r"['\"“”]([^'\"“”]{4,80})['\"“”]")


class PodcastSignal(BaseModel):
    """Strict output schema for tweet → podcast signal extraction."""

    is_podcast_clip: bool = False
    host: str | None = None
    show: str | None = None
    guest: str | None = None
    topic_hint: str | None = None
    topics: list[str] = Field(default_factory=list)
    streaming_links: list[str] = Field(default_factory=list)
    clip_keywords: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sentiment: str = "neutral"  # 'positive' | 'neutral' | 'negative'

    @field_validator("topics", "streaming_links", "clip_keywords")
    @classmethod
    def _strip_dedup(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for s in v:
            t = (s or "").strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out


# Type alias for an LLM enricher: takes tweet text + heuristic result, returns enriched.
LLMEnricher = Callable[[str, PodcastSignal], Awaitable[PodcastSignal]]


def _heuristic_signal(tweet_text: str) -> PodcastSignal:
    text = tweet_text or ""
    if not text:
        return PodcastSignal()

    clip_kws = list({m.lower() for m in CLIP_KEYWORDS_RE.findall(text)})
    has_spotify_pod = bool(SPOTIFY_PODCAST_HOST.search(text))
    has_apple = bool(APPLE_PODCAST_HOST.search(text))
    has_youtube = bool(YOUTUBE_HOST.search(text))

    streaming = []
    for m in re.finditer(r"https?://\S+", text):
        url = m.group(0)
        if "spotify.com" in url or "apple.com" in url or "youtu" in url:
            streaming.append(url)

    # Host detection
    host_entry: HostEntry | None = find_host(text)
    host_name = host_entry.canonical if host_entry else None
    show_name = host_entry.show if host_entry else None

    # Host x Guest pattern
    guest: str | None = None
    pair_m = HOST_X_GUEST_RE.search(text)
    if pair_m:
        a, b = pair_m.group(1).strip(), pair_m.group(2).strip()
        if host_entry and a.lower().startswith(host_entry.canonical.split()[0].lower()):
            guest = b
        elif host_entry and b.lower().startswith(host_entry.canonical.split()[0].lower()):
            guest = a

    # Topic hint from quoted text
    topic_hint = None
    qm = QUOTED_TOPIC_RE.search(text)
    if qm:
        topic_hint = qm.group(1).strip()

    topics = detect_topics(text)
    if host_entry:
        topics = list(dict.fromkeys([*host_entry.topics, *topics]))  # dedup, preserve order

    is_clip = bool(clip_kws) or has_spotify_pod or has_apple or (
        has_youtube and bool(host_entry)
    )

    confidence = 0.0
    if has_spotify_pod:
        confidence += 0.5
    if host_entry:
        confidence += 0.3
    if clip_kws:
        confidence += 0.15
    if guest:
        confidence += 0.05
    confidence = min(round(confidence, 2), 0.95)

    return PodcastSignal(
        is_podcast_clip=is_clip,
        host=host_name,
        show=show_name,
        guest=guest,
        topic_hint=topic_hint,
        topics=topics,
        streaming_links=streaming,
        clip_keywords=clip_kws,
        confidence=confidence,
        sentiment="neutral",
    )


async def extract_podcast_signals(
    tweet_text: str,
    *,
    llm_enricher: LLMEnricher | None = None,
    escalate_below: float = 0.5,
) -> PodcastSignal:
    """Extract podcast signals from a tweet, escalating to LLM only when needed."""
    base = _heuristic_signal(tweet_text)
    if not base.is_podcast_clip and base.confidence < 0.2:
        return base
    if llm_enricher is None or base.confidence >= escalate_below:
        return base
    try:
        return await llm_enricher(tweet_text, base)
    except Exception:
        return base


# ---- A ready-to-use Grok enricher (mirrors djx/analyzer/grok.py pattern) ----

PROMPT = (
    "Analyze this tweet for podcast-related content. Return JSON ONLY with these keys:\n"
    "  is_podcast_clip (bool)\n"
    "  host (string|null) — the podcast host's name if mentioned\n"
    "  show (string|null) — the show name if mentioned\n"
    "  guest (string|null) — the guest's name if mentioned\n"
    "  topic_hint (string|null) — a short phrase capturing what the clip is about\n"
    "  topics (string[]) — high-level topics: comedy, interview, neuroscience, "
    "self-improvement, business, politics, true-crime, philosophy, ai, health, music, sports, etc.\n"
    "  streaming_links (string[])\n"
    "  clip_keywords (string[])\n"
    "  confidence (number 0..1)\n"
    '  sentiment ("positive"|"neutral"|"negative")\n\n'
    "Tweet: {tweet}"
)


def make_grok_enricher(api_key: str, model: str = "grok-4-fast"):
    """Factory that returns an LLMEnricher backed by xAI Grok."""
    import httpx

    async def enrich(tweet_text: str, base: PodcastSignal) -> PodcastSignal:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Return only strict JSON."},
                        {"role": "user", "content": PROMPT.format(tweet=tweet_text)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
            )
            r.raise_for_status()
            payload = r.json()
            data = json.loads(payload["choices"][0]["message"]["content"])
            try:
                merged = PodcastSignal.model_validate(data)
                if base.confidence > merged.confidence:
                    merged.confidence = base.confidence
                return merged
            except Exception:
                return base

    return enrich
