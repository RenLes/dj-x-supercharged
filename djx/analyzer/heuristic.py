from __future__ import annotations

import re
from typing import cast
from urllib.parse import urlparse

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.schema import Energy, Mood, ReleaseType, TweetAnalysis

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
HASHTAG_RE = re.compile(r"#(\w+)")
MENTION_RE = re.compile(r"@(\w+)")
QUOTED_RE = re.compile(r"['\"“”‘’]([^'\"“”‘’]{2,80})['\"“”‘’]")

STREAMING_HOSTS = {
    "open.spotify.com",
    "spoti.fi",
    "music.apple.com",
    "tidal.com",
    "soundcloud.com",
    "youtube.com",
    "youtu.be",
    "music.youtube.com",
    "deezer.com",
    "bandcamp.com",
}

RELEASE_KEYWORDS = [
    ("album", "album"),
    ("ep ", "ep"),
    (" ep,", "ep"),
    ("single", "single"),
    ("track", "single"),
]
RELEASE_VERBS_RE = re.compile(
    r"\b(out\s+now|dropping|drops|new\s+(single|album|ep|track)|"
    r"pre[-\s]?save|link\s+in\s+bio|just\s+released|listen\s+now|"
    r"available\s+now|stream\s+(it|now))\b",
    re.IGNORECASE,
)

HYPE_RE = re.compile(r"\b(hype|fire|banger|insane|crazy|let'?s go|wild|huge)\b", re.IGNORECASE)
CHILL_RE = re.compile(r"\b(chill|mellow|smooth|lo[-\s]?fi|relax|cozy|sunday)\b", re.IGNORECASE)
DARK_RE = re.compile(r"\b(dark|haunt|gloom|moody|shadow|ghost)\b", re.IGNORECASE)
ROMANTIC_RE = re.compile(r"\b(love|romance|heart|kiss|sweet|valentine)\b", re.IGNORECASE)
AGGRO_RE = re.compile(r"\b(rage|angry|fight|aggressive|brutal|savage)\b", re.IGNORECASE)
ENERGETIC_RE = re.compile(r"\b(dance|club|party|edm|workout|gym|pump)\b", re.IGNORECASE)


class HeuristicAnalyzer(BaseAnalyzer):
    """Pure-regex analyzer. No network. Fast. Deterministic."""

    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        return self.analyze_sync(tweet_text)

    @staticmethod
    def analyze_sync(tweet_text: str) -> TweetAnalysis:
        text = tweet_text or ""
        urls = URL_RE.findall(text)
        streaming_links = [u for u in urls if _is_streaming(u)]
        hashtags = HASHTAG_RE.findall(text)
        mentions = MENTION_RE.findall(text)
        quoted = [m.strip() for m in QUOTED_RE.findall(text)]

        release_type, is_new_release = _detect_release(text)
        if streaming_links and not is_new_release:
            is_new_release = True
            release_type = release_type or "single"

        mood, energy = _classify_mood_energy(text)

        confidence = _confidence(
            has_streaming=bool(streaming_links),
            has_release_verb=bool(RELEASE_VERBS_RE.search(text)),
            has_quoted=bool(quoted),
            tokens=len(text.split()),
        )

        return TweetAnalysis(
            artists=mentions,
            tracks=quoted,
            is_new_release=is_new_release,
            release_type=release_type,
            streaming_links=streaming_links,
            mood=cast(Mood, mood),
            energy_level=cast(Energy, energy),
            recommended_artists=[],
            hashtags=hashtags,
            confidence=confidence,
        )


def _is_streaming(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return False
    if host.startswith("www."):
        host = host[4:]
    return any(host == h or host.endswith("." + h) for h in STREAMING_HOSTS)


def _detect_release(text: str) -> tuple[ReleaseType | None, bool]:
    lower = text.lower()
    found_release = bool(RELEASE_VERBS_RE.search(lower))
    rtype: ReleaseType | None = None
    for needle, label in RELEASE_KEYWORDS:
        if needle in lower:
            rtype = label  # type: ignore[assignment]
            break
    if rtype is None and found_release:
        rtype = "single"
    return rtype, found_release


def _classify_mood_energy(text: str) -> tuple[str, str]:
    if HYPE_RE.search(text):
        return "hype", "high"
    if AGGRO_RE.search(text):
        return "aggressive", "high"
    if ENERGETIC_RE.search(text):
        return "energetic", "high"
    if DARK_RE.search(text):
        return "dark", "medium"
    if ROMANTIC_RE.search(text):
        return "romantic", "medium"
    if CHILL_RE.search(text):
        return "chill", "low"
    return "neutral", "medium"


def _confidence(*, has_streaming: bool, has_release_verb: bool, has_quoted: bool, tokens: int) -> float:
    score = 0.3
    if has_streaming:
        score += 0.3
    if has_release_verb:
        score += 0.2
    if has_quoted:
        score += 0.1
    if tokens >= 8:
        score += 0.05
    return round(min(score, 0.95), 2)
