from __future__ import annotations

import re
from collections import Counter

from djx.analyzer.schema import TweetAnalysis

# Heuristics to skip obvious non-music handles before we even probe Spotify.
NON_MUSIC_HANDLE_RE = re.compile(
    r"^("
    r"\w*(NFL|NBA|MLB|NHL|NRL|AFL|FIFA|UFC|ESPN|F1|PGA)\w*"
    r"|DraftKings\w*|FanDuel\w*"
    r"|\w*News\w*|\w*Politics?\w*|CNN\w*|BBC\w*|Fox\w*|NYTimes\w*|WSJ\w*"
    r"|\w*Crypto\w*|\w*Coin\w*|\w*Bitcoin\w*|\w*Trader\w*"
    r"|elonmusk|realdonaldtrump|potus|whitehouse"
    r")$",
    re.IGNORECASE,
)


def detect_viral_artists(
    analyses: list[TweetAnalysis],
    *,
    min_mentions: int = 3,
    boost_release_mentions: int = 2,
) -> list[tuple[str, int]]:
    """Find artists mentioned frequently across recent tweets.

    Returns [(artist_name, score), ...] sorted by score desc. Filters out
    handles that are obviously not music artists (sports teams, news orgs,
    politicians) via a regex pass — Spotify cross-checking happens in
    ``filter_via_spotify`` for the cases the regex doesn't catch.
    """
    counts: Counter[str] = Counter()
    for a in analyses:
        for name in a.artists:
            if NON_MUSIC_HANDLE_RE.match(name):
                continue
            counts[name] += 1
        for name in a.recommended_artists:
            if NON_MUSIC_HANDLE_RE.match(name):
                continue
            counts[name] += 1
        if a.is_new_release:
            for name in a.artists:
                if NON_MUSIC_HANDLE_RE.match(name):
                    continue
                counts[name] += boost_release_mentions
    return [(n, c) for n, c in counts.most_common() if c >= min_mentions]


async def filter_via_spotify(
    candidates: list[tuple[str, int]],
    spotify,  # SpotifyClient — typed weakly to avoid import cycle
    *,
    name_match_threshold: float = 0.85,
) -> list[tuple[str, int]]:
    """Drop names that don't resolve to a real Spotify artist.

    For each candidate, run a lightweight artist search. Keep only those whose
    first hit's name closely matches the candidate (case-insensitive ratio).
    """
    out: list[tuple[str, int]] = []
    for name, count in candidates:
        try:
            r = await spotify.search(name, type_="artist", limit=1)
        except Exception:
            continue
        items = r.get("artists", {}).get("items", [])
        if not items:
            continue
        hit_name = items[0].get("name", "").lower().strip()
        if not hit_name:
            continue
        ratio = _name_ratio(name.lower().strip(), hit_name)
        if ratio >= name_match_threshold:
            out.append((items[0]["name"], count))
    return out


def _name_ratio(a: str, b: str) -> float:
    """Cheap similarity: 1.0 if equal; partial credit for substring containment."""
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.9
    # Fall back to token-set overlap
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta | tb), 1)
