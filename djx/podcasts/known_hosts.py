"""A small curated database of well-known podcast hosts and their shows.

Used to anchor regex matches and to drive the cross-similarity boost.
The list is short on purpose — extending is a one-line PR, and this file is
public-domain data (host names + show names).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HostEntry:
    canonical: str
    show: str
    aliases: tuple[str, ...]
    topics: tuple[str, ...]


HOSTS: tuple[HostEntry, ...] = (
    HostEntry("Joe Rogan", "The Joe Rogan Experience",
              ("rogan", "jre"), ("comedy", "long-form", "interview", "mma", "psychedelics")),
    HostEntry("Lex Fridman", "Lex Fridman Podcast",
              ("lex",), ("ai", "philosophy", "science", "long-form", "interview")),
    HostEntry("Andrew Huberman", "Huberman Lab",
              ("huberman",), ("neuroscience", "health", "self-improvement", "science")),
    HostEntry("Tim Ferriss", "The Tim Ferriss Show",
              ("ferriss", "tferriss"), ("self-improvement", "business", "interview")),
    HostEntry("Sam Harris", "Making Sense",
              ("samharris",), ("philosophy", "neuroscience", "politics")),
    HostEntry("Theo Von", "This Past Weekend",
              ("theovon",), ("comedy", "interview")),
    HostEntry("Bill Simmons", "The Bill Simmons Podcast",
              ("simmons",), ("sports", "nba", "interview")),
    HostEntry("Ben Shapiro", "The Ben Shapiro Show",
              ("benshapiro",), ("politics", "news", "conservative")),
    HostEntry("Trevor Noah", "What Now? with Trevor Noah",
              ("trevornoah",), ("comedy", "politics", "interview")),
    HostEntry("Conan O'Brien", "Conan O'Brien Needs a Friend",
              ("conanobrien", "conan"), ("comedy", "interview")),
    HostEntry("Jay Shetty", "On Purpose",
              ("jayshetty",), ("self-improvement", "spirituality", "interview")),
    HostEntry("Dax Shepard", "Armchair Expert",
              ("daxshepard",), ("interview", "psychology", "comedy")),
    HostEntry("Marc Maron", "WTF with Marc Maron",
              ("marcmaron",), ("comedy", "interview")),
    HostEntry("Alex Cooper", "Call Her Daddy",
              ("alexcooper", "callherdaddy"), ("relationships", "interview", "lifestyle")),
    HostEntry("Steven Bartlett", "The Diary of a CEO",
              ("stevenbartlett",), ("business", "self-improvement", "interview")),
    HostEntry("Patrick Bet-David", "PBD Podcast",
              ("patrickbetdavid",), ("business", "politics", "entrepreneurship")),
    HostEntry("Chris Williamson", "Modern Wisdom",
              ("chriswillx",), ("self-improvement", "interview", "health")),
    HostEntry("Shawn Ryan", "Shawn Ryan Show",
              ("shawnryan",), ("military", "interview", "true-crime")),
    HostEntry("Bert Kreischer", "Bertcast",
              ("bertkreischer",), ("comedy", "interview")),
    HostEntry("Logan Paul", "IMPAULSIVE",
              ("loganpaul",), ("interview", "lifestyle")),
)

# Cross-similarity clusters — when one host scores high, similar hosts get a small boost.
SIMILAR_HOSTS: dict[str, tuple[str, ...]] = {
    "Joe Rogan": ("Theo Von", "Bert Kreischer", "Lex Fridman", "Logan Paul"),
    "Lex Fridman": ("Joe Rogan", "Sam Harris", "Andrew Huberman", "Tim Ferriss"),
    "Andrew Huberman": ("Lex Fridman", "Tim Ferriss", "Chris Williamson"),
    "Tim Ferriss": ("Andrew Huberman", "Lex Fridman", "Steven Bartlett", "Chris Williamson"),
    "Sam Harris": ("Lex Fridman", "Andrew Huberman"),
    "Theo Von": ("Joe Rogan", "Bert Kreischer", "Marc Maron"),
    "Bert Kreischer": ("Theo Von", "Joe Rogan"),
    "Marc Maron": ("Conan O'Brien", "Theo Von", "Dax Shepard"),
    "Conan O'Brien": ("Marc Maron", "Dax Shepard"),
    "Dax Shepard": ("Marc Maron", "Conan O'Brien"),
    "Steven Bartlett": ("Tim Ferriss", "Patrick Bet-David", "Chris Williamson"),
    "Patrick Bet-David": ("Steven Bartlett", "Ben Shapiro"),
    "Chris Williamson": ("Andrew Huberman", "Tim Ferriss", "Steven Bartlett"),
    "Alex Cooper": ("Logan Paul",),
    "Bill Simmons": (),
    "Trevor Noah": ("Conan O'Brien",),
    "Jay Shetty": ("Steven Bartlett",),
    "Ben Shapiro": ("Patrick Bet-David",),
    "Shawn Ryan": ("Joe Rogan",),
    "Logan Paul": ("Alex Cooper", "Joe Rogan"),
}


def find_host(text: str) -> HostEntry | None:
    """Return the first known host matched (canonical name, alias, or show)."""
    lowered = text.lower()
    for h in HOSTS:
        if h.canonical.lower() in lowered:
            return h
        if h.show.lower() in lowered:
            return h
        for alias in h.aliases:
            if alias.lower() in lowered:
                return h
    return None


TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "comedy": ("comedy", "stand-up", "standup", "funny", "joke"),
    "interview": ("interview", "conversation", "chat", "guest"),
    "neuroscience": ("brain", "neuroscience", "neural", "neuron", "dopamine"),
    "self-improvement": ("habits", "productivity", "self-improvement", "growth", "mindset"),
    "business": ("business", "entrepreneur", "startup", "ceo", "founder"),
    "politics": ("politics", "election", "policy", "senate", "congress", "white house"),
    "true-crime": ("murder", "crime", "killer", "investigation", "cold case"),
    "philosophy": ("philosophy", "philosopher", "ethics", "stoicism", "meaning"),
    "ai": ("ai", "artificial intelligence", "llm", "openai", "anthropic", "claude", "gpt"),
    "health": ("health", "fitness", "sleep", "nutrition", "wellness"),
    "music": ("music", "album", "song", "artist", "rapper", "singer"),
    "sports": ("nba", "nfl", "soccer", "football", "basketball", "ufc", "mma"),
    "psychology": ("psychology", "therapy", "trauma", "anxiety", "mental health"),
    "spirituality": ("spirituality", "meditation", "mindfulness", "buddhism"),
}


def detect_topics(text: str) -> list[str]:
    """Return topics whose keywords appear in the text."""
    lowered = text.lower()
    out: list[str] = []
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw in lowered:
                out.append(topic)
                break
    return out
