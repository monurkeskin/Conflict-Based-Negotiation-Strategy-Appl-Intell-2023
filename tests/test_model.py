"""Differential tests against the frozen public implementation, at every prefix."""

import hashlib
import random
from itertools import product
from pathlib import Path

import pytest
from reference.loader import load_reference

from cbom import ConflictBasedOpponentModel, Preference

ReferenceModel = load_reference()


def assert_models_equal(model, reference):
    assert model.value_ordering == reference.value_ordering
    assert model.issue_ordering == reference.issue_ordering
    assert model.preference.issue_weights == pytest.approx(reference.preference._issue_weights)
    for issue in model.reference.issues:
        assert model.preference.value_weights[issue] == pytest.approx(reference.preference._value_weights[issue])
    assert model.comparisons == len(reference.CM)


def compare_sequence(profile, offers):
    current = ConflictBasedOpponentModel(profile)
    reference = ReferenceModel(profile)
    assert_models_equal(current, reference)
    for offer in offers:
        current.update(offer)
        reference.update(offer, 0.0)
        assert_models_equal(current, reference)
    return current, reference


def test_frozen_public_algorithm_hash():
    source = Path(__file__).parent / "reference" / "negolog_v2_cbom.py"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "5de4b82cf09660d6d8d54eab5b730086f353e90d796b2abd8281be97889ad336"
    )


@pytest.mark.parametrize("seed", range(12))
def test_random_histories_match_full_comparison_map(seed):
    rng = random.Random(seed)
    count = 1 + seed % 4
    sizes = [2 + (seed + i) % 3 for i in range(count)]
    raw = [rng.random() for _ in range(count)]
    weights = {f"i{i}": w / sum(raw) for i, w in enumerate(raw)}
    values = {f"i{i}": {f"v{v}": rng.choice([0., .3, .7, 1.]) for v in range(n)}
              for i, n in enumerate(sizes)}
    profile = Preference(weights, values)
    offers = [{i: rng.choice(profile.domain[i]) for i in profile.issues} for _ in range(65)]
    compare_sequence(profile, offers)


def test_history_boundary_retains_older_evidence():
    # Almost all repeated bids: cheap reference replay still crosses the real 1000 cap.
    profile = Preference({"x": 1.}, {"x": {"a": 1., "b": 0.}})
    offers = [{"x": "a"}] * 1001 + [{"x": "b"}, {"x": "a"}, {"x": "b"}]
    current, reference = compare_sequence(profile, offers)
    assert len(current._history) == len(reference.opponent_offer_history) == 1000
    assert current.evidence_cells == 2
    assert current.comparisons > 1000


def test_multi_issue_history_boundary_reinterprets_persistent_evidence():
    profile = Preference(dict.fromkeys(["x", "y", "z"], 1 / 3), {
        i: {"a": 1., "b": 0.} for i in ["x", "y", "z"]
    })
    repeated = {"x": "a", "y": "a", "z": "b"}
    offers = [repeated] * 1001 + [
        {"x": "b", "y": "b", "z": "a"},
        {"x": "b", "y": "a", "z": "a"},
        {"x": "a", "y": "b", "z": "b"},
    ]
    current, _ = compare_sequence(profile, offers)
    assert current._joint_counts
    assert current.comparisons > 1000


@pytest.mark.parametrize("utility", [0., .5, 1.])
def test_tied_initialization_and_cycles(utility):
    profile = Preference({"x": .5, "y": .5}, {
        "x": dict.fromkeys(["a", "b", "c"], utility), "y": dict.fromkeys(["q", "r"], utility)
    })
    bids = [dict(zip(profile.issues, values)) for values in product(*profile.domain.values())]
    compare_sequence(profile, bids + list(reversed(bids)) + bids * 3)


def test_invalid_offer_is_atomic_and_input_is_copied():
    profile = Preference({"x": 1.}, {"x": {"a": 1., "b": 0.}})
    model = ConflictBasedOpponentModel(profile)
    with pytest.raises(ValueError):
        model.update({"x": "unknown"})
    assert model.observations == model.comparisons == 0
    bid = {"x": "a"}
    model.update(bid)
    bid["x"] = "b"
    assert list(model._history) == [("a",)]


def test_singleton_domain_and_weight_snapshot():
    model = ConflictBasedOpponentModel(Preference({"x": 1.}, {"x": {"a": 1.}}))
    previous = model.preference
    for _ in range(20):
        model.update({"x": "a"})
    assert model.preference.utility({"x": "a"}) == 1.
    assert model.evidence_cells == model.comparisons == 0
    with pytest.raises(TypeError):
        previous.issue_weights["x"] = 0


@pytest.mark.parametrize("size", [0, -1, True, 2.5, None])
def test_invalid_history_size(size):
    with pytest.raises(ValueError):
        ConflictBasedOpponentModel(Preference({"x": 1.}, {"x": {"a": 1.}}), size)
