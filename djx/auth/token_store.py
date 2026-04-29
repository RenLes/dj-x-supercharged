from __future__ import annotations

import contextlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None = None
    expires_at: float = 0.0
    scope: str = ""
    token_type: str = "Bearer"

    def is_expired(self, skew: int = 60) -> bool:
        return self.expires_at - skew < time.time()


class TokenStore:
    """JSON file at ~/.djx/tokens.json. Two top-level keys: 'spotify', 'x'."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, dict]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
        with contextlib.suppress(OSError):
            os.chmod(self.path, 0o600)

    def get(self, provider: str) -> TokenSet | None:
        raw = self._read().get(provider)
        if not raw:
            return None
        return TokenSet(
            access_token=raw.get("access_token", ""),
            refresh_token=raw.get("refresh_token"),
            expires_at=float(raw.get("expires_at", 0)),
            scope=raw.get("scope", ""),
            token_type=raw.get("token_type", "Bearer"),
        )

    def set(self, provider: str, tokens: TokenSet) -> None:
        data = self._read()
        data[provider] = asdict(tokens)
        self._write(data)

    def clear(self, provider: str | None = None) -> None:
        if provider is None:
            self.path.unlink(missing_ok=True)
            return
        data = self._read()
        data.pop(provider, None)
        self._write(data)

    def status(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for provider in ("spotify", "x"):
            t = self.get(provider)
            if t is None:
                out[provider] = "missing"
            elif t.is_expired():
                out[provider] = "expired"
            else:
                out[provider] = "valid"
        return out
