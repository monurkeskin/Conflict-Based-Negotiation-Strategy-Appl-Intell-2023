"""Behavioral checks of the published bidding policy and live CBOM integration."""

import math

import pytest

from cbom.model import ConflictBasedOpponentModel
from cbom.preferences import Preference
from cbom.strategy import BEHAVIOR_WEIGHTS, CBOMAgent


def profile(values=None, reservation=0.0):
    return Preference({"item": 1.0}, {"item": values or {"a": 1, "b": .8, "c": .6, "d": 0}},
                      reservation=reservation)


def bid(value):
    return {"item": value}


def test_opening_is_own_maximum_with_selection_trace():
    agent = CBOMAgent(profile())
    action = agent.act(0)
    assert action.kind == "offer"
    assert action.bid == bid("a")
    assert action.own_utility == 1
    assert action.selection.exact is True
    assert agent.own_history == (bid("a"),)


def test_default_parameters_and_quadratic_time_equation():
    agent = CBOMAgent(profile())
    assert (agent.p0, agent.p1, agent.p2, agent.p3) == (.9, .7, .4, .5)
    assert agent.model_threshold == 3
    assert agent.epsilon == .02
    assert agent.time_based(0) == .9
    assert agent.time_based(.5) == pytest.approx(.675)
    assert agent.time_based(1) == .4
    assert sum(BEHAVIOR_WEIGHTS[3]) == pytest.approx(.99)


def test_hybrid_uses_last_four_weighted_changes_oldest_to_newest():
    preference = profile({"top": 1, "old": .9, "u1": .1, "u2": .2, "u3": .4, "u4": .3, "u5": .6})
    agent = CBOMAgent(preference)
    agent.act(0)
    for index, value in enumerate(["old", "u1", "u2", "u3", "u4", "u5"], 1):
        agent.receive(bid(value), index / 20)
    # Last differences are +.1,+.2,-.1,+.3, not the older -.8 change.
    delta = .05 * .1 + .15 * .2 - .3 * .1 + .5 * .3
    expected = .75 * (1 - .75 * delta) + .25 * .675
    assert agent.target_utility(.5) == pytest.approx(expected)


@pytest.mark.parametrize("utilities,weights", [
    ([.1, .3], [1]),
    ([.1, .3, .2], [.25, .75]),
    ([.1, .3, .2, .4], [.11, .22, .66]),
])
def test_short_histories_use_inherited_weight_table(utilities, weights):
    preference = profile({"top": 1, **{str(i): u for i, u in enumerate(utilities)}})
    agent = CBOMAgent(preference)
    agent.act(0)
    for i in range(len(utilities)):
        agent.receive(bid(str(i)), .1)
    delta = sum((b - a) * w for a, b, w in zip(utilities, utilities[1:], weights))
    assert agent.target_utility(.5) == pytest.approx(.75 * (1 - .75 * delta) + .25 * .675)


def test_real_model_receives_warmup_offers_and_changes_selected_offer():
    ready = CBOMAgent(profile(), model_threshold=3, epsilon=1)
    warming = CBOMAgent(profile(), model_threshold=4, epsilon=1)
    for agent in (ready, warming):
        agent.act(0)
        for t in [.1, .2, .3]:
            agent.receive(bid("d"), t)
        assert isinstance(agent.model, ConflictBasedOpponentModel)
        assert agent.model.observations == 3
    modeled = ready.act(.3)
    own_only = warming.act(.3)
    assert modeled.bid == bid("c")  # .6 * .75 > .8 * .5
    assert own_only.bid == bid("b")
    assert modeled.selection.opponent_utility == pytest.approx(.75)
    assert own_only.selection.opponent_utility is None


def test_received_single_issue_concession_updates_the_live_estimate():
    agent = CBOMAgent(profile())
    before = agent.model.preference.utility(bid("b"))
    agent.receive(bid("b"), .1)
    agent.receive(bid("c"), .2)
    assert agent.model.comparisons == 1
    assert agent.model.preference.utility(bid("b")) > before
    assert agent.model.preference.utility(bid("b")) > agent.model.preference.utility(bid("c"))


def test_paper_acceptance_uses_historical_floor_not_only_next_candidate():
    agent = CBOMAgent(profile({"a": 1, "b": .8, "c": .6, "d": .5, "e": 0}), model_threshold=99)
    assert agent.act(0).bid == bid("a")
    assert agent.act(.8).bid == bid("d")
    agent.receive(bid("a"), .81)
    agent.receive(bid("d"), .82)
    action = agent.act(.82)
    assert action.selection.own_utility > .5
    assert action.kind == "accept"
    assert action.bid == bid("d")
    assert len(agent.own_history) == 2  # An unsent candidate is not an offer.


def test_equal_candidate_utility_is_acceptable():
    agent = CBOMAgent(profile())
    agent.receive(bid("a"), 0)
    assert agent.act(0).kind == "accept"
    assert agent.own_history == ()


def test_reservation_prevents_acceptance_and_below_floor_offers():
    agent = CBOMAgent(profile(reservation=.85), epsilon=1)
    agent.act(0)
    agent.receive(bid("b"), .5)
    action = agent.act(.5)
    assert action.kind == "end"
    assert agent.target_utility(1) >= .85


def test_no_feasible_outcome_ends_without_invalid_offer():
    agent = CBOMAgent(profile({"only": .2}, reservation=.4))
    assert agent.act(0).kind == "end"
    assert agent.own_history == ()


@pytest.mark.parametrize("mode", ["exact", "sampled"])
def test_near_reservation_candidate_does_not_hide_a_feasible_offer(mode):
    preference = profile({"best": .9, "near": .8 - 5e-13, "feasible": .85, "bad": 0},
                         reservation=.8)
    agent = CBOMAgent(preference, epsilon=0, mode=mode, sample_size=64, seed=0)
    assert agent.act(0).bid == bid("best")
    agent.receive(bid("bad"), .8)
    action = agent.act(.8)
    assert action.kind == "offer"
    assert action.bid == bid("feasible")
    assert action.own_utility >= preference.reservation


def test_exhausted_pool_ends_without_repeating_an_offer():
    agent = CBOMAgent(profile({"only": 1}))
    assert agent.act(0).kind == "offer"
    action = agent.act(.1)
    assert action.kind == "end"
    assert action.reason == "candidate pool exhausted"


def test_exhausted_pool_can_accept_an_offer_at_historical_floor():
    agent = CBOMAgent(profile({"only": 1}))
    agent.act(0)
    agent.receive(bid("only"), .1)
    action = agent.act(.1)
    assert action.kind == "accept"
    assert action.selection is None


def test_deadline_can_accept_but_does_not_send_new_offer():
    agent = CBOMAgent(profile())
    agent.act(0)
    agent.receive(bid("d"), 1)
    assert agent.act(1).kind == "end"
    acceptable = CBOMAgent(profile())
    acceptable.receive(bid("a"), 1)
    assert acceptable.act(1).kind == "accept"


def test_input_and_history_mutation_do_not_change_agent_state():
    agent = CBOMAgent(profile())
    received = bid("d")
    agent.receive(received, .1)
    received["item"] = "a"
    external_history = agent.opponent_history
    external_history[0]["item"] = "b"
    assert agent.opponent_history == (bid("d"),)
    action = agent.act(.1)
    action.bid["item"] = "d"
    assert agent.own_history == (bid("a"),)


@pytest.mark.parametrize("time", [-.1, 1.1, math.nan, math.inf, True, "0.5"])
def test_invalid_receive_time_is_atomic(time):
    agent = CBOMAgent(profile())
    with pytest.raises(ValueError):
        agent.receive(bid("d"), time)
    assert agent.model.observations == 0
    assert agent.opponent_history == ()


def test_decreasing_time_and_invalid_bid_leave_state_unchanged():
    agent = CBOMAgent(profile())
    agent.receive(bid("d"), .3)
    with pytest.raises(ValueError, match="nondecreasing"):
        agent.receive(bid("c"), .2)
    with pytest.raises(ValueError):
        agent.receive(bid("missing"), .8)
    assert agent.model.observations == 1
    # The rejected .8 input did not advance the clock.
    assert agent.act(.3).kind == "offer"
    with pytest.raises(ValueError, match="nondecreasing"):
        agent.act(.2)


def test_session_is_closed_after_terminal_action():
    agent = CBOMAgent(profile())
    agent.receive(bid("a"), .1)
    agent.act(.1)
    with pytest.raises(RuntimeError, match="ended"):
        agent.receive(bid("b"), .2)
    with pytest.raises(RuntimeError, match="ended"):
        agent.act(.2)


def test_counteroffer_expires_received_offer_until_received_again():
    agent = CBOMAgent(profile(), model_threshold=99)
    agent.receive(bid("b"), 0.)
    assert agent.act(0.).kind == "offer"
    # A later callback without a new opponent offer cannot accept the old one.
    assert agent.act(.8).kind == "offer"
    agent.receive(bid("b"), .81)
    assert agent.act(.81).kind == "accept"


@pytest.mark.parametrize("kwargs", [
    {"p0": -1}, {"p1": math.nan}, {"p2": 2}, {"p3": True},
    {"epsilon": -.1}, {"model_threshold": 0}, {"model_threshold": True},
    {"model_threshold": 2.5},
])
def test_invalid_strategy_parameters_fail_early(kwargs):
    with pytest.raises(ValueError):
        CBOMAgent(profile(), **kwargs)


def test_incompatible_opponent_model_domain_is_rejected():
    other = ConflictBasedOpponentModel(profile({"different": 1}))
    with pytest.raises(ValueError, match="same domain"):
        CBOMAgent(profile(), model=other)
