"""Differential CPython 3.10 TimSort checks, including cyclic comparisons."""

from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from functools import cmp_to_key
from pathlib import Path

import pytest
from test_java_parity import Bridge, assert_equivalent, random_profile, state
from test_java_parity import java_jar as _shared_java_jar

from cbom.model import ConflictBasedOpponentModel

REFERENCE = Path(__file__).parent / "reference/cpython310-sort.json"
java_jar = _shared_java_jar  # Register the shared build fixture with this module.


def digest_order(values):
    return hashlib.sha256(",".join(map(str, values)).encode("ascii")).hexdigest()


def digest_state(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


def comparison(kind, seed, left, right):
    if kind == "cycle":
        if left == right:
            return 0
        low, high = sorted((left, right))
        score = (low * 1103515245 + high * 12345 + seed * 214013) % 101
        result = -1 if score < 33 else (0 if score < 66 else 1)
        return result if left < right else -result
    if kind == "groups":
        left = (left * 17 + seed) % 13
        right = (right * 17 + seed) % 13
    return (left > right) - (left < right)


def python_oracle(case):
    trace = hashlib.sha256()
    count = 0

    def compare(left, right):
        nonlocal count
        count += 1
        trace.update(f"{left},{right};".encode("ascii"))
        return comparison(case["kind"], case["seed"], left, right)

    result = sorted(case["input"], key=cmp_to_key(compare))
    return {"order_sha256": digest_order(result), "comparisons": count,
            "comparison_sha256": trace.hexdigest()}


def write_reference():
    """Generate independent C-runtime expectations, never from the Java port."""
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 10):
        raise SystemExit("Generate this reference only with CPython 3.10")
    cases = []
    for size in [0, 1, 2, 31, 63, 64, 65, 80, 127, 128, 200, 511, 1000]:
        for seed in range(8):
            for kind in ["cycle", "groups", "ascending"]:
                values = list(range(size))
                if seed % 4 == 1:
                    values.reverse()
                elif seed % 4 == 2:
                    random.Random(seed + size).shuffle(values)
                elif seed % 4 == 3:
                    # Reordered natural runs exercise stack collapse and gallops.
                    blocks = [values[start:start + 31] for start in range(0, size, 31)]
                    random.Random(seed).shuffle(blocks)
                    values = [value for block in blocks for value in block]
                case = {"id": f"{kind}-{size}-{seed}", "kind": kind, "seed": seed, "input": values}
                case["expected"] = python_oracle(case)
                cases.append(case)
    model_cases = []
    for seed, values in [(27, 80), (19, 64), (81, 127), (104, 128), (103, 200)]:
        profile = random_profile(seed, issues=1, values=values)
        model = ConflictBasedOpponentModel(profile)
        rng = random.Random(451)
        case = {"seed": seed, "values": values, "profile": profile.to_dict(),
                "offer_seed": 451, "initial_sha256": digest_state(state(model)), "steps": []}
        for step in range(180):
            bid = {"i0": rng.choice(profile.domain["i0"])}
            model.update(bid)
            case["steps"].append({"bid": bid, "state_sha256": digest_state(state(model))})
        model_cases.append(case)
    payload = {"generator": "tests/test_java_long_order.py:write_reference",
               "python": sys.version, "algorithm": "CPython 3.10 TimSort",
               "source": "https://github.com/python/cpython/blob/v3.10.20/Objects/listobject.c",
               "cases": cases, "model_cases": model_cases}
    REFERENCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} C-runtime reference cases: {REFERENCE}")


JAVA_PROBE = r'''
package org.cbom;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
public final class OrderProbe {
    private static int compare(String kind, long seed, int left, int right) {
        if (kind.equals("cycle")) {
            if (left == right) return 0;
            int low = Math.min(left, right), high = Math.max(left, right);
            long score = (low * 1103515245L + high * 12345L + seed * 214013L) % 101;
            int result = score < 33 ? -1 : (score < 66 ? 0 : 1);
            return left < right ? result : -result;
        }
        if (kind.equals("groups")) {
            left = (int)((left * 17L + seed) % 13);
            right = (int)((right * 17L + seed) % 13);
        }
        return Integer.compare(left, right);
    }
    public static void main(String[] args) throws Exception {
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = input.readLine()) != null) {
            Map<String,Object> request = Json.object(Json.parse(line));
            List<Integer> values = new ArrayList<>();
            for (Object value : (List<?>)request.get("input")) values.add(((Number)value).intValue());
            String kind = (String)request.get("kind");
            long seed = ((Number)request.get("seed")).longValue();
            MessageDigest trace = MessageDigest.getInstance("SHA-256");
            int[] count = {0};
            List<Integer> ordered = StableOrder.sorted(values, (left, right) -> {
                count[0]++; trace.update((left + "," + right + ";").getBytes(StandardCharsets.US_ASCII));
                return compare(kind, seed, left, right);
            });
            StringJoiner joined = new StringJoiner(",");
            for (int value : ordered) joined.add(Integer.toString(value));
            byte[] order = MessageDigest.getInstance("SHA-256").digest(joined.toString().getBytes(StandardCharsets.US_ASCII));
            System.out.println(Json.stringify(Json.map("order_sha256", HexFormat.of().formatHex(order),
                    "comparisons", count[0], "comparison_sha256", HexFormat.of().formatHex(trace.digest()))));
        }
    }
}
'''


@pytest.fixture(scope="module")
def sort_probe(java_jar, tmp_path_factory):
    directory = tmp_path_factory.mktemp("sort-probe")
    source = directory / "OrderProbe.java"
    source.write_text(JAVA_PROBE, encoding="utf-8")
    subprocess.run(["javac", "--release", "17", "-cp", str(java_jar[1]), "-d", str(directory),
                    str(source)], check=True, capture_output=True, text=True)
    process = subprocess.Popen([java_jar[0], "-cp", str(java_jar[1]) + os.pathsep + str(directory),
                                "org.cbom.OrderProbe"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        yield process
    finally:
        process.communicate(timeout=10)
        assert process.returncode == 0


if __name__ == "__main__":
    # The CPython 3.10 generator may bootstrap an absent reference file.
    CASES, MODEL_CASES = [], []
else:
    # A missing or incomplete packaged oracle must fail collection, not silently
    # replace hundreds of parity checks with an empty parametrization.
    REFERENCE_DATA = json.loads(REFERENCE.read_text(encoding="utf-8"))
    CASES = REFERENCE_DATA["cases"]
    MODEL_CASES = REFERENCE_DATA["model_cases"]
    if not CASES or not MODEL_CASES:
        raise ValueError("The CPython 3.10 sort and model reference must be nonempty")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_order_and_exact_comparison_schedule_match_cpython310(sort_probe, case):
    sort_probe.stdin.write(json.dumps(case) + "\n")
    sort_probe.stdin.flush()
    line = sort_probe.stdout.readline()
    assert line, "Java sort probe exited unexpectedly"
    assert json.loads(line) == case["expected"]
    if sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 10):
        assert python_oracle(case) == case["expected"]


@pytest.mark.parametrize("case", MODEL_CASES, ids=lambda case: f"{case['seed']}-{case['values']}")
def test_long_cyclic_model_prefixes_match_cpython310(java_jar, case):
    profile = random_profile(case["seed"], issues=1, values=case["values"])
    assert profile.to_dict() == case["profile"]
    model = ConflictBasedOpponentModel(profile)
    live_oracle = sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 10)
    with Bridge(java_jar, profile) as bridge:
        assert digest_state(bridge.initial) == case["initial_sha256"]
        for index, step in enumerate(case["steps"]):
            actual = bridge.request("receive", bid=step["bid"], t=index / len(case["steps"]))
            assert digest_state(actual) == step["state_sha256"]
            if live_oracle:
                model.update(step["bid"])
                assert_equivalent(actual, state(model))


if __name__ == "__main__":
    write_reference()
