"""Measure synthetic update cost and verify every prefix against public CBOM.

Run from a source checkout: python benchmarks/compare_models.py --output result.json
Timing is a local implementation comparison, not a paper experiment.
"""

import argparse
import json
import platform
import random
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

from cbom import ConflictBasedOpponentModel, Preference

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from reference.loader import load_reference  # noqa: E402


def profile_and_offers(rounds, seed, issues=3, values=4):
    rng = random.Random(seed)
    profile = Preference({f"i{i}": 1 / issues for i in range(issues)}, {
        f"i{i}": {f"v{v}": v / (values - 1) for v in range(values)} for i in range(issues)
    })
    offers = [{i: rng.choice(profile.domain[i]) for i in profile.issues} for _ in range(rounds)]
    return profile, offers


def evaluate(rounds, seed):
    profile, offers = profile_and_offers(rounds, seed)
    current = ConflictBasedOpponentModel(profile)
    baseline = load_reference()(profile)
    times = [0., 0.]
    for bid in offers:
        start = time.perf_counter()
        baseline.update(bid, 0.)
        times[0] += time.perf_counter() - start
        start = time.perf_counter()
        current.update(bid)
        times[1] += time.perf_counter() - start
        assert current.value_ordering == baseline.value_ordering
        assert current.issue_ordering == baseline.issue_ordering
        assert current.preference.issue_weights == baseline.preference._issue_weights
        assert current.preference.value_weights == baseline.preference._value_weights
    return {"seed": seed, "reference_seconds": times[0], "aggregated_seconds": times[1],
            "comparisons": current.comparisons, "evidence_cells": current.evidence_cells,
            "every_prefix_equal": True}


def peak_bytes(rounds):
    profile, offers = profile_and_offers(rounds, 0)
    result = {}
    for name, constructor in [("reference", load_reference()), ("aggregated", ConflictBasedOpponentModel)]:
        tracemalloc.start()
        model = constructor(profile)
        for bid in offers:
            model.update(bid, 0.)
        result[name] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, nargs="+", default=[50, 100, 200])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("outputs/model-benchmark.json"))
    args = parser.parse_args()
    if min(args.rounds) < 1 or args.repeats < 1:
        parser.error("rounds and repeats must be positive")
    report = {"kind": "synthetic implementation benchmark", "platform": platform.platform(),
              "machine": platform.machine(), "python": platform.python_version(),
              "domain": {"issues": 3, "values_per_issue": 4, "outcomes": 64}, "measurements": []}
    for rounds in args.rounds:
        trials = [evaluate(rounds, seed) for seed in range(args.repeats)]
        row = {"rounds": rounds, "trials": trials,
               "reference_seconds_median": statistics.median(t["reference_seconds"] for t in trials),
               "aggregated_seconds_median": statistics.median(t["aggregated_seconds"] for t in trials)}
        row["median_time_ratio"] = row["reference_seconds_median"] / row["aggregated_seconds_median"]
        report["measurements"].append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "trials"}), flush=True)
    report["separate_tracemalloc_peak_bytes"] = {"rounds": max(args.rounds), **peak_bytes(max(args.rounds))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
