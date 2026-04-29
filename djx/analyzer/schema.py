"""Strict JSON schema for tweet analyses (matches user spec §5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Mood = Literal["hype", "chill", "dark", "energetic", "romantic", "aggressive", "neutral"]
Energy = Literal["high", "medium", "low"]
ReleaseType = Literal["single", "album", "ep"]


class TweetAnalysis(BaseModel):
    """Output schema for a single tweet analysis."""

    artists: list[str] = Field(default_factory=list)
    tracks: list[str] = Field(default_factory=list)
    is_new_release: bool = False
    release_type: ReleaseType | None = None
    streaming_links: list[str] = Field(default_factory=list)
    mood: Mood = "neutral"
    energy_level: Energy = "medium"
    recommended_artists: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("artists", "tracks", "streaming_links", "recommended_artists", "hashtags")
    @classmethod
    def _strip_and_dedup(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            s = (item or "").strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out
