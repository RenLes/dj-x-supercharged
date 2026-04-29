from __future__ import annotations

import re
from collections import Counter

# Yahoo WOEIDs for X's trends-by-woeid endpoint. Subset — extend as needed.
WOEID = {
    "worldwide": 1,
    "united_states": 23424977,
    "united_kingdom": 23424975,
    "canada": 23424775,
    "australia": 23424748,
    "brazil": 23424768,
    "mexico": 23424900,
    "germany": 23424829,
    "france": 23424819,
    "spain": 23424950,
    "italy": 23424853,
    "japan": 23424856,
    "south_korea": 23424868,
    "india": 23424848,
    "indonesia": 23424846,
    "nigeria": 23424908,
    "south_africa": 23424942,
    "fiji": 23424813,
    "new_zealand": 23424916,
}

# Country names + common adjectives -> normalized country key.
COUNTRY_PATTERNS = {
    "united_states": r"\b(usa|u\.s\.a?|america|american|states?)\b",
    "united_kingdom": r"\b(uk|britain|british|england|english|london)\b",
    "canada": r"\b(canada|canadian|toronto|montreal)\b",
    "australia": r"\b(australia|australian|aussie|sydney|melbourne)\b",
    "brazil": r"\b(brazil|brazilian|brasil|rio|s[aã]o\s*paulo)\b",
    "mexico": r"\b(mexico|mexican|mexicano)\b",
    "germany": r"\b(germany|german|berlin|munich)\b",
    "france": r"\b(france|french|paris|francais)\b",
    "spain": r"\b(spain|spanish|espa[nñ]ol|madrid|barcelona)\b",
    "italy": r"\b(italy|italian|italiano|rome|milan)\b",
    "japan": r"\b(japan|japanese|tokyo|osaka|kyoto)\b",
    "south_korea": r"\b(korea|korean|k-?pop|seoul)\b",
    "india": r"\b(india|indian|mumbai|delhi|bollywood)\b",
    "nigeria": r"\b(nigeria|nigerian|naija|lagos|afrobeats?)\b",
    "fiji": r"\b(fiji|fijian|suva|nadi)\b",
    "new_zealand": r"\b(new\s*zealand|kiwi|auckland|wellington)\b",
}

_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in COUNTRY_PATTERNS.items()}


def detect_locations(texts: list[str]) -> list[tuple[str, int]]:
    """Return [(country_key, hit_count), ...] sorted by frequency."""
    counts: Counter[str] = Counter()
    for txt in texts:
        if not txt:
            continue
        for key, pat in _COMPILED.items():
            if pat.search(txt):
                counts[key] += 1
    return counts.most_common()


def woeid_for_country(country_key: str) -> int | None:
    return WOEID.get(country_key)
