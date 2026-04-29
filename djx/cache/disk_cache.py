from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class DiskCache:
    """Tiny JSON-on-disk cache with TTL. Keyed by namespace + sorted params."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        ns_dir = self.root / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir / f"{h}.json"

    @staticmethod
    def _stable_key(parts: dict[str, Any]) -> str:
        return json.dumps(parts, sort_keys=True, default=str)

    def get(self, namespace: str, parts: dict[str, Any], ttl_seconds: int) -> Any | None:
        path = self._path(namespace, self._stable_key(parts))
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() - float(payload.get("_ts", 0)) > ttl_seconds:
            return None
        return payload.get("value")

    def set(self, namespace: str, parts: dict[str, Any], value: Any) -> None:
        path = self._path(namespace, self._stable_key(parts))
        path.write_text(
            json.dumps({"_ts": time.time(), "value": value}, default=str),
            encoding="utf-8",
        )

    def clear(self, namespace: str | None = None) -> int:
        target = self.root / namespace if namespace else self.root
        if not target.exists():
            return 0
        n = 0
        for p in target.rglob("*.json"):
            p.unlink(missing_ok=True)
            n += 1
        return n
