# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Podcast Pulse**: clip-to-episode resolver + persistent affinity engine.
  - `djx/podcasts/signals.py` — hybrid regex + LLM extractor for hosts, shows, guests, topics, sentiment.
  - `djx/podcasts/affinity.py` — JSON-backed persistent scoring with 30-day recency decay and similar-host cross-boost.
  - `djx/podcasts/resolver.py` — Spotify episode/show search with strength-scored matches.
  - `djx/podcasts/known_hosts.py` — curated database of ~20 well-known hosts and a similarity graph.
  - New CLI commands: `djx podcasts {resolve, daily, weekly, affinity, explain}`.
- `SpotifyClient.search_episodes()`, `search_shows()`, `show_episodes()`.
- `XClient.home_timeline()`, `personalized_trends()`, `trends_by_woeid()`.
- New playlist builders: `daily_pulse`, `weekly_resonance`, `mood_mirror`, `viral_surge`.
- `djx/insights/` module: `window`, `trends`, `location`, `virality`.

### Fixed
- Spotify candidate expansion no longer relies on `/v1/artists/{id}/top-tracks` and `/v1/artists/{id}/related-artists` (Spotify dev-mode 403). Pivoted to `/v1/search?type=track&q=artist:"X"` plus `/v1/me/top/tracks` and curated chart playlists.
- Score collapse: identical 5.40 ranks → introduced source-quality bonuses and deterministic hash-based jitter.
- Virality detector no longer counts non-music X handles (sports teams, news orgs, politicians) — uses regex pre-filter plus optional Spotify cross-check.
- Music trend regex significantly expanded (NewMusicFriday, banger, NowPlaying, etc.).
- `liked_tweets` no longer sends an unsupported `start_time` parameter (X returns 400). Filtering is in-memory via `within_window()`.

## [0.1.0] - 2026-04-29

### Added
- Initial release.
- Spotify + X OAuth 2.0 PKCE flows with loopback server, Vercel-hosted fallback, and manual-paste fallback.
- `XClient` (X API v2) and `SpotifyClient` (Web API v1) with disk-cached reads, 401 refresh, 429 `Retry-After` honoring, and X 403 graceful degradation.
- `BaseAnalyzer` extension point with three built-in implementations:
  - `HeuristicAnalyzer` (regex-only, deterministic, offline).
  - `GrokAnalyzer` (xAI Grok with structured JSON output).
  - `HybridAnalyzer` (heuristic-first; escalates to LLM when confidence < 0.6).
- Custom recommender (Spotify `/v1/recommendations` is deprecated):
  - Seed pool aggregator that weights top artists, artist tweets, and your liked tweets.
  - Candidate expansion via Spotify search + related-artists + artist top-tracks.
  - Ranker with novelty bonus, recently-played penalty, and per-artist diversity cap.
- CLI (`djx`): `run`, `auth spotify`, `auth x`, `auth status`, `clear-cache`, `version`.
- Contract test (`tests/test_base_analyzer.py::analyzer_contract`) for forks shipping custom analyzers.
- Vercel callback page for headless OAuth flows.
- Examples for plugging in Anthropic Claude or OpenAI as the analyzer LLM.
