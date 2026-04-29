from __future__ import annotations

import datetime as dt
from pathlib import Path

from rich.console import Console

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTIVITY_LOG = PROJECT_ROOT / ".agent_memory" / "activity.log"


def _zeros_for_lines(lines: int) -> str:
    return "0" * max(1, (lines + 99) // 100)


def log_activity(code: str, target: str = "", note: str = "", lines: int = 0) -> None:
    """Append a one-line entry to .agent_memory/activity.log per workspace CLAUDE.md."""
    ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    if code in {"1", "2", "M"} and lines:
        code = f"{code}{_zeros_for_lines(lines)}"
    line = f"{ts} {code} {target} {note}".rstrip() + "\n"
    with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
        f.write(line)
