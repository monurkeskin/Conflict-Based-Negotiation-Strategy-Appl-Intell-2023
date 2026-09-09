"""Executable cross-language regressions against the native JDK-only implementation."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from cbom.cli import example_profile, negotiate
from cbom.model import ConflictBasedOpponentModel
from cbom.preferences import Preference
from cbom.strategy import CBOMAgent

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_REFERENCE = ROOT / "tests/reference/cpython310-protocol.json"
IS_CPYTHON310 = sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 10)
live_cpython310 = pytest.mark.skipif(
    not IS_CPYTHON310,
    reason="Java targets CPython 3.10 sorting; complete frozen protocol traces run on every runtime",
)


def read_protocol_reference():
    """Decode lossless object interning; every request/response field is retained."""
    data = json.loads(PROTOCOL_REFERENCE.read_text(encoding="utf-8"))
    if data["format"] != "cbom-cpython310-protocol-v1":
        raise ValueError("Unsupported protocol reference format")
    nodes = data["nodes"]
    decoded = {}

    def decode(value):
        if isinstance(value, dict):
            if set(value) == {"$ref"}:
                index = value["$ref"]
                if index not in decoded:
                    decoded[index] = decode(nodes[index])
                return decoded[index]
            return {key: decode(item) for key, item in value.items()}
        if isinstance(value, list):
            return [decode(item) for item in value]
        return value

    payload = decode(data["payload"])
    if len(payload["traces"]) != 26 or len(payload["cli"]) != 5:
        raise ValueError("The CPython 3.10 protocol reference is incomplete")
    return payload


if __name__ == "__main__":
    PROTOCOL_TRACES, CLI_REFERENCE = [], {}
else:
    _reference = read_protocol_reference()
    PROTOCOL_TRACES, CLI_REFERENCE = _reference["traces"], _reference["cli"]


@pytest.fixture(scope="module")
def java_jar():
    java = shutil.which("java")
    if not java or not shutil.which("javac") or not shutil.which("jar"):
        if os.environ.get("CBOM_REQUIRE_JAVA"):
            pytest.fail("CBOM_REQUIRE_JAVA is set, but a JDK is unavailable")
        pytest.skip("JDK 17+ required for cross-language tests")
    version = subprocess.run([java, "-version"], capture_output=True, text=True)
    if version.returncode:
        if os.environ.get("CBOM_REQUIRE_JAVA"):
            pytest.fail(version.stderr)
        pytest.skip("A working JDK is required, not an OS placeholder launcher")
    subprocess.run([sys.executable, str(ROOT / "java" / "build.py")], check=True, capture_output=True, text=True)
    return java, ROOT / "java" / "build" / "cbom.jar"


class Bridge:
    def __init__(self, java_jar, profile, **options):
        self._close_sent = False
        self.process = subprocess.Popen(
            [java_jar[0], "-jar", str(java_jar[1]), "serve"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        self.initial = self.request("init", profile=profile.to_dict(), options=options)

    def request(self, operation, expect_error=False, **kwargs):
        self.process.stdin.write(json.dumps({"op": operation, **kwargs}) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        assert line, self.process.stderr.read()
        reply = json.loads(line)
        assert reply["ok"] is not expect_error, reply
        self.last_response = reply
        if operation == "close":
            self._close_sent = True
        return reply if expect_error else reply["result"]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.process.poll() is None and not self._close_sent:
            self.request("close")
        self.process.communicate(timeout=10)
        assert self.process.returncode == 0


def assert_equivalent(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_equivalent(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            assert_equivalent(a, b)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=1e-14, rel=0)
    else:
        assert actual == expected


def state(model):
    return {"preference": model.preference.to_dict(), "issue_ordering": model.issue_ordering,
            "value_ordering": model.value_ordering, "observations": model.observations,
            "comparisons": model.comparisons, "evidence_cells": model.evidence_cells}


def random_profile(seed, issues=4, values=5):
    rng = random.Random(seed)
    weights = [rng.randint(0, 10) for _ in range(issues)]
    if not sum(weights):
        weights[0] = 1
    total = sum(weights)
    return Preference({f"i{i}": w / total for i, w in enumerate(weights)},
                      {f"i{i}": {f"v{v}": rng.choice([0, .25, .5, .75, 1])
                                 for v in range(values)} for i in range(issues)})


@pytest.mark.parametrize("seed", range(12))
@live_cpython310
def test_model_prefix_parity_with_ties_cycles_and_capped_history(java_jar, seed):
    profile = random_profile(seed, issues=1 + seed % 5, values=1 + seed % 6)
    rng = random.Random(seed + 991)
    cap = [1, 2, 7, 1000][seed % 4]
    model = ConflictBasedOpponentModel(profile, history_size=cap)
    with Bridge(java_jar, profile, history_size=cap) as bridge:
        assert_equivalent(bridge.initial, state(model))
        for step in range(120):
            bid = {i: rng.choice(profile.domain[i]) for i in profile.issues}
            model.update(bid)
            assert_equivalent(bridge.request("receive", bid=bid, t=step / 120), state(model))


@pytest.mark.parametrize("seed", [47, 93])
@live_cpython310
def test_model_default_history_boundary(java_jar, seed):
    profile = random_profile(seed, issues=3, values=4)
    rng = random.Random(seed)
    model = ConflictBasedOpponentModel(profile)
    with Bridge(java_jar, profile) as bridge:
        for step in range(1010):
            bid = {i: rng.choice(profile.domain[i]) for i in profile.issues}
            model.update(bid)
            assert_equivalent(bridge.request("receive", bid=bid, t=step / 1010), state(model))


@pytest.mark.parametrize("issues,values", [(63, 2), (2, 63)])
@live_cpython310
def test_short_sort_boundary_parity(java_jar, issues, values):
    profile = random_profile(281, issues=issues, values=values)
    model = ConflictBasedOpponentModel(profile)
    rng = random.Random(452)
    with Bridge(java_jar, profile, mode="sampled", sample_size=16) as bridge:
        assert_equivalent(bridge.initial, state(model))
        for step in range(12):
            bid = {i: rng.choice(profile.domain[i]) for i in profile.issues}
            model.update(bid)
            assert_equivalent(bridge.request("receive", bid=bid, t=step / 12), state(model))


@pytest.mark.parametrize("mode", ["exact", "sampled"])
@pytest.mark.parametrize("seed", [0, 1, -97, 2**65 + 13])
@live_cpython310
def test_strategy_decisions_and_integer_seeded_sample_parity(java_jar, mode, seed):
    profile = random_profile(abs(seed) % 30, issues=4, values=5)
    options = {"mode": mode, "seed": seed, "sample_size": 80}
    agent = CBOMAgent(profile, **options)
    rng = random.Random(seed)
    with Bridge(java_jar, profile, **options) as bridge:
        for step in range(50):
            t = step / 49
            if step:
                # Keep receiving poor offers so the strategy explores its policy.
                bid = {i: min(profile.domain[i], key=profile.value_weights[i].get) for i in profile.issues}
                if step % 5 == 0:
                    bid = {i: rng.choice(profile.domain[i]) for i in profile.issues}
                agent.receive(bid, t)
                assert_equivalent(bridge.request("receive", bid=bid, t=t), state(agent.model))
            action = agent.act(t)
            assert_equivalent(bridge.request("act", t=t), asdict(action))
            if action.kind != "offer":
                break


def test_boundary_and_stale_offer_regressions(java_jar):
    profile = Preference({"x": 1}, {"x": {"best": .9, "near": .8 - 5e-13, "feasible": .85, "bad": 0}}, .8)
    for mode in ["exact", "sampled"]:
        with Bridge(java_jar, profile, mode=mode, sample_size=100, epsilon=0) as bridge:
            assert bridge.request("act", t=0)["bid"] == {"x": "best"}
            bridge.request("receive", bid={"x": "bad"}, t=.8)
            assert bridge.request("act", t=.8)["bid"] == {"x": "feasible"}
    profile = Preference({"x": 1}, {"x": {"a": 1, "b": .8, "c": .5, "d": 0}})
    with Bridge(java_jar, profile) as bridge:
        bridge.request("receive", bid={"x": "b"}, t=0)
        assert bridge.request("act", t=0)["kind"] == "offer"
        assert bridge.request("act", t=.8)["kind"] == "offer"
        bridge.request("receive", bid={"x": "b"}, t=.9)
        assert bridge.request("act", t=.9)["kind"] == "accept"
        bridge.request("act", t=1, expect_error=True)


def test_invalid_requests_are_atomic_and_server_recovers(java_jar):
    profile = example_profile("a")
    with Bridge(java_jar, profile) as bridge:
        before = bridge.request("inspect")
        for request in [dict(op="receive", bid={}, t=0), dict(op="receive", bid=profile.best_bid(), t=-.1),
                        dict(op="act", t=True), dict(op="unrecognized")]:
            op = request.pop("op")
            bridge.request(op, expect_error=True, **request)
            assert bridge.request("inspect") == before
        for options in [{"sample_size": 1.5}, {"history_size": True}, {"model_threshold": 1.0},
                        {"mode": []}, {"p0": 10**400}, {"seed": "password"}, {"unknown": 1}]:
            bridge.request("init", profile=profile.to_dict(), options=options, expect_error=True)
            assert bridge.request("inspect") == before
        bridge.request("receive", bid=profile.best_bid(), t=.5)
        before = bridge.request("inspect")
        bridge.request("receive", bid=profile.best_bid(), t=.4, expect_error=True)
        assert bridge.request("inspect") == before


@pytest.mark.parametrize("mode", ["auto", "exact", "sampled"])
def test_standalone_java_demo_matches_python(java_jar, tmp_path, mode):
    target = tmp_path / "demo.json"
    subprocess.run([java_jar[0], "-jar", str(java_jar[1]), "demo", "--search-mode", mode,
                    "--sample-size", "40", "--output", str(target)], check=True, capture_output=True, text=True)
    expected = CLI_REFERENCE[f"demo-{mode}"]
    if IS_CPYTHON310:
        assert_equivalent(expected, negotiate(example_profile("a"), example_profile("b"),
                                             mode=mode, sample_size=40))
    assert_equivalent(json.loads(target.read_text()), expected)


def test_native_self_tests_and_standalone_learning(java_jar, tmp_path):
    subprocess.run([java_jar[0], "-jar", str(java_jar[1]), "self-test"], check=True, capture_output=True, text=True)
    profile = example_profile("a")
    bids = [profile.best_bid(), {i: profile.domain[i][-1] for i in profile.issues}] * 10
    model = ConflictBasedOpponentModel(profile)
    for bid in bids:
        model.update(bid)
    profile_path = tmp_path / "profile.json"
    offers_path = tmp_path / "offers.jsonl"
    output = tmp_path / "estimated.json"
    profile_path.write_text(json.dumps(profile.to_dict()), encoding="utf-8")
    offers_path.write_text("\n".join(map(json.dumps, bids)), encoding="utf-8")
    subprocess.run([java_jar[0], "-jar", str(java_jar[1]), "learn", "--profile", str(profile_path),
                    "--offers", str(offers_path), "--output", str(output)], check=True, capture_output=True, text=True)
    expected = CLI_REFERENCE["learn"]
    if IS_CPYTHON310:
        assert_equivalent(expected, model.preference.to_dict())
    assert_equivalent(json.loads(output.read_text()), expected)


@live_cpython310
def test_large_acyclic_value_order_and_large_domain(java_jar):
    # 80 values exceeds the Python short-list sorting path, but acyclic evidence
    # has one total ordering and therefore remains equivalent.
    profile = Preference({"x": 1}, {"x": {f"v{i}": i / 79 for i in range(80)}})
    model = ConflictBasedOpponentModel(profile)
    with Bridge(java_jar, profile) as bridge:
        for step in range(80):
            bid = {"x": f"v{79-step}"}
            model.update(bid)
            assert_equivalent(bridge.request("receive", bid=bid, t=step / 80), state(model))
    # No enumeration: 50^10 outcomes, sampled fixed pool only.
    profile = random_profile(892, issues=10, values=50)
    options = {"mode": "auto", "sample_size": 150, "seed": 19}
    python = CBOMAgent(profile, **options)
    with Bridge(java_jar, profile, **options) as bridge:
        assert_equivalent(bridge.request("act", t=0), asdict(python.act(0)))


def test_long_cyclic_order_is_deterministic(java_jar):
    profile = random_profile(27, issues=1, values=80)
    rng = random.Random(451)
    bids = [{"i0": rng.choice(profile.domain["i0"])} for _ in range(160)]
    with Bridge(java_jar, profile) as first, Bridge(java_jar, profile) as second:
        for step, bid in enumerate(bids):
            a = first.request("receive", bid=bid, t=step / len(bids))
            b = second.request("receive", bid=bid, t=step / len(bids))
            assert a == b


@pytest.mark.parametrize("size", [18_000, 47_000])
def test_many_singleton_issues_do_not_exhaust_java_stack(java_jar, size):
    profile = Preference({f"i{i}": 1 / size for i in range(size)},
                         {f"i{i}": {"only": 1} for i in range(size)})
    with Bridge(java_jar, profile, mode="exact") as bridge:
        assert sum(bridge.initial["preference"]["issueWeights"].values()) == pytest.approx(1)
        action = bridge.request("act", t=0)
        assert action["kind"] == "offer"
        assert action["bid"] == profile.best_bid()
        assert action["selection"]["candidate_count"] == 1
        assert action["own_utility"] == profile.utility(profile.best_bid())
        assert bridge.request("act", t=.1)["kind"] == "end"


def test_standalone_demo_serializes_arbitrary_integer_seed(java_jar, tmp_path):
    output = tmp_path / "huge-seed-demo.json"
    seed = 10**400
    subprocess.run([java_jar[0], "-jar", str(java_jar[1]), "demo", "--seed", str(seed),
                    "--rounds", "1", "--output", str(output)],
                   check=True, capture_output=True, text=True)
    actual = json.loads(output.read_text())
    assert actual["settings"]["seed"] == seed
    expected = CLI_REFERENCE["demo-huge-seed"]
    if IS_CPYTHON310:
        assert_equivalent(expected, negotiate(example_profile("a"), example_profile("b"), rounds=1, seed=seed))
    assert_equivalent(actual, expected)


@pytest.mark.parametrize("escape", ["+123", "-123", "１２３４", "00g0"])
def test_protocol_rejects_nonhex_unicode_escapes_atomically(java_jar, escape):
    profile = example_profile("a")
    with Bridge(java_jar, profile) as bridge:
        before = bridge.request("inspect")
        raw = ('{"op":"init","profile":{"issueWeights":{"\\u' + escape
               + '":1},"issues":{"\\u' + escape + '":{"v":1}}}}\n')
        bridge.process.stdin.write(raw)
        bridge.process.stdin.flush()
        reply = json.loads(bridge.process.stdout.readline())
        assert not reply["ok"]
        assert "Invalid Unicode escape" in reply["error"]
        assert bridge.request("inspect") == before


@pytest.mark.parametrize("case", PROTOCOL_TRACES, ids=lambda case: case["id"])
def test_complete_protocol_matches_frozen_cpython310_on_every_runtime(java_jar, case):
    initial = case["events"][0]
    assert initial["request"]["op"] == "init"
    profile = Preference.from_dict(initial["request"]["profile"])
    with Bridge(java_jar, profile, **initial["request"]["options"]) as bridge:
        assert_equivalent(bridge.last_response, initial["response"])
        for index, event in enumerate(case["events"][1:]):
            request, expected = event["request"], event["response"]
            bridge.request(request["op"], **{key: value for key, value in request.items() if key != "op"})
            try:
                assert_equivalent(bridge.last_response, expected)
            except AssertionError as error:
                raise AssertionError(f"{case['id']} event {index + 1}: {request}") from error


def write_protocol_reference():
    """Record canonical Python 3.10 execution; Java is never called by this writer.

    Full requests/responses are stored with lossless object interning to avoid
    repeating profiles and rankings thousands of times. Regenerate deliberately
    with `python tests/test_java_parity.py --write-protocol-reference` on 3.10.
    """
    if not IS_CPYTHON310:
        raise SystemExit("Generate the protocol reference only with actual CPython 3.10")
    traces = []
    active_id = ""

    class Recorder:
        def __init__(self, _java, profile, **options):
            self.events = []
            self.options = dict(options)
            core_options = dict(options)
            history_size = core_options.pop("history_size", 1000)
            self.agent = CBOMAgent(profile, model=ConflictBasedOpponentModel(profile, history_size), **core_options)
            self.initial = self.record({"op": "init", "profile": profile.to_dict(), "options": options},
                                       state(self.agent.model))

        def record(self, request, result):
            response = {"ok": True, "result": result}
            if request["op"] == "act":
                response["action"] = result
            # Detach mutable model ordering containers at this prefix.
            self.events.append(json.loads(json.dumps({"request": request, "response": response})))
            return result

        def request(self, op, **kwargs):
            if op == "receive":
                self.agent.receive(kwargs["bid"], kwargs["t"])
                result = state(self.agent.model)
            elif op == "act":
                result = asdict(self.agent.act(kwargs["t"]))
            elif op == "inspect":
                result = state(self.agent.model)
            else:
                raise ValueError(f"Unexpected recorder operation: {op}")
            return self.record({"op": op, **kwargs}, result)

        def __enter__(self):
            return self

        def __exit__(self, error_type, *_):
            if error_type is not None:
                return
            self.record({"op": "close"}, None)
            traces.append({"id": active_id, "events": self.events})

    global Bridge
    original_bridge = Bridge
    try:
        Bridge = Recorder
        for seed in range(12):
            active_id = f"model-prefix-{seed}"
            test_model_prefix_parity_with_ties_cycles_and_capped_history(None, seed)
        for seed in [47, 93]:
            active_id = f"history-boundary-{seed}"
            test_model_default_history_boundary(None, seed)
        for issues, values in [(63, 2), (2, 63)]:
            active_id = f"rank-boundary-{issues}-{values}"
            test_short_sort_boundary_parity(None, issues, values)
        for seed in [0, 1, -97, 2**65 + 13]:
            for mode in ["exact", "sampled"]:
                active_id = f"strategy-{mode}-{seed}"
                test_strategy_decisions_and_integer_seeded_sample_parity(None, mode, seed)
        active_id = "large-acyclic-80"
        before = len(traces)
        test_large_acyclic_value_order_and_large_domain(None)
        traces[before + 1]["id"] = "large-sampled-domain"
    finally:
        Bridge = original_bridge

    cli = {f"demo-{mode}": negotiate(example_profile("a"), example_profile("b"), mode=mode, sample_size=40)
           for mode in ["auto", "exact", "sampled"]}
    cli["demo-huge-seed"] = negotiate(example_profile("a"), example_profile("b"), rounds=1, seed=10**400)
    profile = example_profile("a")
    model = ConflictBasedOpponentModel(profile)
    for bid in [profile.best_bid(), {i: profile.domain[i][-1] for i in profile.issues}] * 10:
        model.update(bid)
    cli["learn"] = model.preference.to_dict()
    payload = {"traces": traces, "cli": cli}
    nodes, indices = [], {}

    def intern(value):
        if isinstance(value, dict):
            node = {key: intern(item) for key, item in value.items()}
        elif isinstance(value, list):
            node = [intern(item) for item in value]
        else:
            return value
        key = json.dumps(node, ensure_ascii=True, separators=(",", ":"))
        if key not in indices:
            indices[key] = len(nodes)
            nodes.append(node)
        return {"$ref": indices[key]}

    packed = intern(payload)
    sources = {f"src/cbom/{name}.py": hashlib.sha256((ROOT / f"src/cbom/{name}.py").read_bytes()).hexdigest()
               for name in ["model", "strategy", "preferences", "search", "cli"]}
    header = {"format": "cbom-cpython310-protocol-v1", "generator": "tests/test_java_parity.py:write_protocol_reference",
              "python": sys.version, "source_sha256": sources,
              "description": "Complete actual CPython 3.10 requests and responses. Object interning is lossless; no Java-generated expectations or omitted state fields.",
              "trace_count": len(traces), "event_count": sum(len(case["events"]) for case in traces),
              "cli_count": len(cli), "nodes": nodes, "payload": packed}
    # One interned node per line keeps source diffs readable without excessive whitespace.
    node_text = ",\n".join(json.dumps(node, ensure_ascii=True, separators=(",", ":")) for node in nodes)
    del header["nodes"]
    prefix = json.dumps(header, indent=2)[:-2]
    PROTOCOL_REFERENCE.write_text(prefix + ',\n  "nodes": [\n' + node_text + '\n  ]\n}\n', encoding="utf-8")
    print(f"Recorded {len(traces)} traces / {header['event_count']} complete protocol events and {len(cli)} CLI results")


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-protocol-reference"]:
        raise SystemExit("Usage: python tests/test_java_parity.py --write-protocol-reference")
    write_protocol_reference()
