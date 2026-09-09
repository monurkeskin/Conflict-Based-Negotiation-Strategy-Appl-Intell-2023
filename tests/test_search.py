"""Candidate search checked against a literal paper-band implementation."""

import math
import random
from itertools import product

import pytest

from cbom import Preference
from cbom.search import CandidatePool, NoAvailableBid


@pytest.fixture
def profile():
    return Preference({"x": .65, "y": .35}, {
        "x": {"a": 1., "b": .45, "c": 0.}, "y": {"d": 1., "e": .2}
    })


@pytest.mark.parametrize("target", [0., .037, .3, .5, .61, .923, 1.])
@pytest.mark.parametrize("use_model", [False, True])
def test_exact_matches_literal_band_expansion(profile, target, use_model):
    opponent = Preference({"x": .3, "y": .7}, {
        "x": {"a": 0., "b": .8, "c": 1.}, "y": {"d": 0., "e": 1.}
    }) if use_model else None
    pool = CandidatePool(profile, mode="exact")
    bids = [dict(zip(profile.issues, vals)) for vals in product(*profile.domain.values())]
    excluded = {profile.validate_bid(profile.best_bid())}
    width = .02
    while True:
        candidates = [b for b in bids if profile.validate_bid(b) not in excluded
                      and target - width - 1e-12 <= profile.utility(b) <= target + width + 1e-12]
        if candidates:
            break
        width += .01
    selection = pool.select(target, excluded=excluded, opponent=opponent)
    def score(b):
        return profile.utility(b) * (opponent.utility(b) if opponent else 1.)
    assert score(selection.bid) == pytest.approx(max(map(score, candidates)))
    assert selection.epsilon == pytest.approx(width)
    assert selection.candidate_count == len(candidates)
    assert selection.exact


def test_model_changes_the_selected_bid(profile):
    pool = CandidatePool(profile)
    inverse = Preference({"x": .7, "y": .3}, {
        "x": {"a": 0., "b": 1., "c": .5}, "y": {"d": .1, "e": 1.}
    })
    own = pool.select(.5, epsilon=1.)
    joint = pool.select(.5, epsilon=1., opponent=inverse)
    assert own.bid != joint.bid
    assert joint.own_utility * joint.opponent_utility > (
        own.own_utility * inverse.utility(own.bid)
    )


def test_large_domain_sampling_is_bounded_and_rng_local():
    issues = [f"i{i}" for i in range(20)]
    profile = Preference(dict.fromkeys(issues, .05), {
        i: {f"v{v}": v / 9 for v in range(10)} for i in issues
    })
    state = random.getstate()
    first = CandidatePool(profile, sample_size=128, seed=17)
    second = CandidatePool(profile, sample_size=128, seed=17)
    assert profile.size == 10 ** 20
    assert not first.exact and first.size <= 128
    assert first._entries == second._entries
    assert random.getstate() == state
    assert first.select(1.).own_utility == pytest.approx(1.)
    with pytest.raises(ValueError, match="exceeds"):
        CandidatePool(profile, mode="exact")


def test_pool_exhaustion_terminates(profile):
    pool = CandidatePool(profile)
    excluded = set()
    for _ in range(profile.size):
        result = pool.select(.5, excluded=excluded)
        excluded.add(profile.validate_bid(result.bid))
    with pytest.raises(NoAvailableBid):
        pool.select(.5, excluded=excluded)


def test_reservation_guard():
    profile = Preference({"x": 1.}, {"x": {"low": .2, "high": .9}}, .8)
    result = CandidatePool(profile).select(.1)
    assert result.bid == {"x": "high"}
    impossible = Preference({"x": 1.}, {"x": {"low": .2}}, .8)
    with pytest.raises(NoAvailableBid):
        CandidatePool(impossible).select(.8)


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -.1, 1.1, True])
def test_invalid_target(profile, invalid):
    with pytest.raises(ValueError):
        CandidatePool(profile).select(invalid)


@pytest.mark.parametrize("count", [10, 20, 100])
def test_large_domain_agent_opening_at_unit_reservation(count):
    from cbom.strategy import CBOMAgent

    profile = Preference({f"i{i}": 1 / count for i in range(count)}, {
        f"i{i}": {"a": 1., "b": 0.} for i in range(count)
    }, reservation=1.)
    action = CBOMAgent(profile, sample_size=32).act(0.)
    assert action.kind == "offer"
    assert action.own_utility == 1.
