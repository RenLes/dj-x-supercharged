from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(path)))


@dataclass
class Config:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str

    x_client_id: str
    x_client_secret: str
    x_redirect_uri: str

    xai_api_key: str
    xai_model: str

    vercel_fallback_url: str
    cache_dir: Path
    tokens_path: Path
    runs_dir: Path

    max_artists: int
    playlist_track_count: int
    request_timeout: int

    missing: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, env_path: str | os.PathLike | None = None) -> Config:
        if env_path is not None:
            load_dotenv(env_path, override=False)
        else:
            load_dotenv(override=False)

        def need(key: str, default: str | None = None) -> str:
            v = os.getenv(key, default)
            return v if v is not None else ""

        cfg = cls(
            spotify_client_id=need("SPOTIFY_CLIENT_ID"),
            spotify_client_secret=need("SPOTIFY_CLIENT_SECRET"),
            spotify_redirect_uri=need("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8765/callback"),
            x_client_id=need("X_CLIENT_ID"),
            x_client_secret=need("X_CLIENT_SECRET"),
            x_redirect_uri=need("X_REDIRECT_URI", "http://127.0.0.1:8765/callback"),
            xai_api_key=need("XAI_API_KEY"),
            xai_model=need("XAI_MODEL", "grok-4-fast"),
            vercel_fallback_url=need("DJX_VERCEL_FALLBACK_URL", ""),
            cache_dir=_expand(need("DJX_CACHE_DIR", "~/.djx/cache")),
            tokens_path=_expand(need("DJX_TOKENS_PATH", "~/.djx/tokens.json")),
            runs_dir=_expand(need("DJX_RUNS_DIR", "~/.djx/runs")),
            max_artists=int(need("DJX_MAX_ARTISTS", "20")),
            playlist_track_count=int(need("DJX_PLAYLIST_TRACK_COUNT", "30")),
            request_timeout=int(need("DJX_REQUEST_TIMEOUT", "30")),
        )
        cfg.missing = cfg._missing_required()
        cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        cfg.runs_dir.mkdir(parents=True, exist_ok=True)
        cfg.tokens_path.parent.mkdir(parents=True, exist_ok=True)
        return cfg

    def _missing_required(self) -> list[str]:
        required = {
            "SPOTIFY_CLIENT_ID": self.spotify_client_id,
            "SPOTIFY_CLIENT_SECRET": self.spotify_client_secret,
            "X_CLIENT_ID": self.x_client_id,
        }
        return [k for k, v in required.items() if not v]
