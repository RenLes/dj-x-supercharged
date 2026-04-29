"""dj-x-supercharged — hybrid Spotify + X playlist generator."""

from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.grok import GrokAnalyzer
from djx.analyzer.heuristic import HeuristicAnalyzer
from djx.analyzer.hybrid import HybridAnalyzer
from djx.analyzer.schema import TweetAnalysis
from djx.clients.spotify import SpotifyClient
from djx.clients.x import XClient
from djx.recommender.playlist import build_playlist
from djx.recommender.score import Recommender

__version__ = "0.1.0"

__all__ = [
    "BaseAnalyzer",
    "GrokAnalyzer",
    "HeuristicAnalyzer",
    "HybridAnalyzer",
    "Recommender",
    "SpotifyClient",
    "TweetAnalysis",
    "XClient",
    "__version__",
    "build_playlist",
]
