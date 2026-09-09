import math

import pytest

from cbom import Preference


@pytest.mark.parametrize("weights,values,reservation", [
    ({}, {}, 0.),
    ({"x": .5}, {"x": {"a": 1.}}, 0.),
    ({"x": 1.}, {"y": {"a": 1.}}, 0.),
    ({"x": 1.}, {"x": {}}, 0.),
    ({"x": 1.}, {"x": {"a": math.nan}}, 0.),
    ({"x": 1.}, {"x": {"a": 1.}}, math.inf),
    ({"x": True}, {"x": {"a": 1.}}, 0.),
])
def test_invalid_profiles(weights, values, reservation):
    with pytest.raises(ValueError):
        Preference(weights, values, reservation)


def test_profile_copies_inputs_and_exports():
    data = {"issueWeights": {"x": 1.}, "issues": {"x": {"a": 1., "b": .4}}, "reservationValue": .2}
    profile = Preference.from_dict(data)
    data["issues"]["x"]["a"] = 0.
    exported = profile.to_dict()
    exported["issues"]["x"]["a"] = .1
    assert profile.utility({"x": "a"}) == 1.
    assert profile.best_bid() == {"x": "a"}
    assert profile.size == 2
    with pytest.raises(AttributeError, match="immutable"):
        profile.issue_weights = {"x": .1}
    with pytest.raises(AttributeError, match="immutable"):
        del profile.issue_weights


@pytest.mark.parametrize("bid", [{}, {"x": "a", "y": "b"}, {"x": None}, {"x": []}, []])
def test_invalid_bid(bid):
    profile = Preference({"x": 1.}, {"x": {"a": 1.}})
    with pytest.raises(ValueError):
        profile.utility(bid)
