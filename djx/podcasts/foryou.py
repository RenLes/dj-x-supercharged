"""Map X 'For You' signals (personalized_trends + categories) into podcast-search topics.

X's `/users/personalized_trends` is the closest thing the v2 API gives us to the
'For You' algorithm — these are the topics X believes the authenticated user is
interested in *right now*. We turn those into queries for Spotify show search,
which gives much better-targeted recommendations than generic topic-keyword
matching against our likes.
"""

from __future__ import annotations

import re
from collections import Counter

# X trend categories → seed search keywords for Spotify podcast search.
# The right-hand side is intentionally short and broad so each maps to many shows.
CATEGORY_TO_PODCAST_TOPICS: dict[str, list[str]] = {
    "News": ["news", "current events", "politics"],
    "Politics": ["politics", "policy", "election"],
    "Sports": ["sports", "sports analysis"],
    "Entertainment": ["entertainment", "pop culture", "celebrity"],
    "Music": ["music", "artist interview"],
    "Business": ["business", "entrepreneurship", "finance"],
    "Technology": ["tech", "technology", "ai"],
    "Science": ["science", "research"],
    "Health": ["health", "wellness"],
    "Gaming": ["gaming", "esports"],
    "Lifestyle": ["lifestyle", "self-improvement"],
    "Crypto": ["crypto", "blockchain", "web3"],
    "Other": [],
}

# Lowercase keyword fragments → podcast-search topics.
KEYWORD_TO_TOPICS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\b(elect|vote|polit|congress|senate|whitehouse|president|trump|biden|harris)\b", re.I),
        ["politics", "election analysis"]),
    (re.compile(r"\b(epa|climate|environment|carbon|emissions)\b", re.I),
        ["climate policy", "environment"]),
    (re.compile(r"\b(stock|nasdaq|nyse|earnings|fed|inflation|recession|gdp)\b", re.I),
        ["finance", "economics"]),
    (re.compile(r"\b(bitcoin|crypto|ethereum|coin|web3|defi|nft)\b", re.I),
        ["crypto", "web3"]),
    (re.compile(r"\b(ai|chatgpt|openai|anthropic|gpt|llm|claude|gemini)\b", re.I),
        ["ai", "artificial intelligence", "tech"]),
    (re.compile(r"\b(nba|nfl|mlb|nhl|nrl|ufc|mma|fifa|football|basketball|soccer)\b", re.I),
        ["sports", "sports analysis"]),
    (re.compile(r"\b(spotify|playlist|song|album|rapper|singer|musician|concert|tour)\b", re.I),
        ["music industry", "artist interview"]),
    (re.compile(r"\b(movie|film|tv|netflix|hbo|disney|oscar|emmy)\b", re.I),
        ["film", "entertainment"]),
    (re.compile(r"\b(podcast|interview|long[- ]form|conversation)\b", re.I),
        ["interview", "conversation"]),
    (re.compile(r"\b(murder|crime|killer|investigation|trial|cold case)\b", re.I),
        ["true crime", "investigation"]),
    (re.compile(r"\b(brain|neuro|dopamine|sleep|focus|meditation|psychology)\b", re.I),
        ["neuroscience", "psychology"]),
    (re.compile(r"\b(startup|founder|ceo|venture|vc|entrepreneur)\b", re.I),
        ["business", "startup", "entrepreneurship"]),
    (re.compile(r"\b(diet|fitness|health|workout|nutrition|wellness|protein)\b", re.I),
        ["health", "fitness"]),
    (re.compile(r"\b(weather|hurricane|earthquake|wildfire|storm)\b", re.I),
        ["news", "current events"]),
    (re.compile(r"\b(spacex|rocket|mars|nasa|astronaut|space)\b", re.I),
        ["space", "science"]),
]


def topics_from_tweet_corpus(tweets: list[dict], *, max_topics: int = 10) -> list[str]:
    """Derive For-You-style topics from tweet text.

    Used when X's `/personalized_trends` is unavailable (free tier / paywalled).
    Runs the same KEYWORD_TO_TOPICS regex matchers against each tweet's text,
    weighted by per-tweet engagement when present.
    """
    weights: Counter[str] = Counter()
    for t in tweets:
        text = t.get("text") or ""
        if not text:
            continue
        # Engagement weight: prefer tweets with more interactions if metrics are present
        m = (t.get("public_metrics") or {})
        engage = (
            int(m.get("like_count", 0))
            + 2 * int(m.get("retweet_count", 0))
            + 3 * int(m.get("quote_count", 0))
        )
        weight = max(1, min(engage // 100, 10))
        for pat, topics in KEYWORD_TO_TOPICS:
            if pat.search(text):
                for tp in topics:
                    weights[tp] += weight
                break
    return [topic for topic, _ in weights.most_common(max_topics)]


def topics_from_personalized_trends(trends: list[dict], *, max_topics: int = 12) -> list[str]:
    """Return a ranked list of podcast-search topic strings derived from trends.

    Ranking: keyword-derived topics weighted by trend post_count_int when present,
    plus a smaller bump from the trend's category mapping. Output is deduplicated
    while preserving descending weight order.
    """
    weights: Counter[str] = Counter()
    for t in trends:
        name = t.get("trend_name", "") or ""
        cat = t.get("category", "") or ""
        score = int(t.get("post_count_int") or _post_count(t.get("post_count")))
        score = max(score, 1)

        # Keyword-derived topics (strongest signal — lifted directly from trend text)
        for pat, topics in KEYWORD_TO_TOPICS:
            if pat.search(name):
                for tp in topics:
                    weights[tp] += score
                break  # only first matching pattern — avoids double-weighting

        # Category-derived topics (broader, lower weight)
        for tp in CATEGORY_TO_PODCAST_TOPICS.get(cat, []):
            weights[tp] += max(score // 4, 1)

    return [topic for topic, _ in weights.most_common(max_topics)]


def _post_count(s: str | None) -> int:
    if not s:
        return 0
    m = re.match(r"\s*([\d.]+)\s*([KMB]?)", s, re.IGNORECASE)
    if not m:
        return 0
    n = float(m.group(1))
    mul = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2).upper()]
    return int(n * mul)
