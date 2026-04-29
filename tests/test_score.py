from collections import Counter

from djx.recommender.candidates import TrackCandidate
from djx.recommender.score import Recommender
from djx.recommender.seeds import SeedPool


def _cand(name: str, artist: str, seed_weight: int, popularity: int = 50, tid: str | None = None):
    return TrackCandidate(
        uri=f"spotify:track:{tid or name}",
        track_id=tid or name,
        name=name,
        artist_name=artist,
        artist_id=f"artist_{artist}",
        popularity=popularity,
        seed_artist=artist,
        seed_weight=seed_weight,
    )


def test_higher_seed_weight_ranks_higher():
    cands = [_cand("low", "A", 1), _cand("high", "B", 9)]
    ranked = Recommender().rank(cands, SeedPool(), target_count=2)
    assert ranked[0].candidate.name == "high"


def test_recently_played_penalty():
    cands = [
        _cand("fresh", "A", 5, popularity=50, tid="t_fresh"),
        _cand("old", "B", 5, popularity=99, tid="t_old"),
    ]
    ranked = Recommender().rank(
        cands, SeedPool(), already_played_track_ids={"t_old"}, target_count=2
    )
    assert ranked[0].candidate.name == "fresh"


def test_diversity_caps_two_per_artist():
    cands = [_cand(f"track{i}", "SameArtist", 5) for i in range(5)]
    cands.append(_cand("solo", "Other", 5))
    ranked = Recommender().rank(cands, SeedPool(), target_count=10)
    artists = [s.candidate.artist_name for s in ranked]
    assert artists.count("SameArtist") <= 2


def test_seed_pool_dominant():
    pool = SeedPool(
        moods=Counter({"hype": 3, "chill": 1}),
        energies=Counter({"high": 5, "low": 2}),
    )
    assert pool.dominant_mood == "hype"
    assert pool.dominant_energy == "high"


def test_target_count_respected():
    cands = [_cand(f"t{i}", f"A{i}", i + 1) for i in range(50)]
    ranked = Recommender().rank(cands, SeedPool(), target_count=10)
    assert len(ranked) == 10
