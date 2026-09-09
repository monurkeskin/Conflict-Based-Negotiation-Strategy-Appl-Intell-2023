# Performance and validation

[Back to README](../README.md) · [Aggregation argument](method.md#why-aggregation-preserves-the-model)

CBOM's comparison evidence is aggregated without changing the pinned public
model's inferred orderings or weights. This removes the list of individual offer
pairs and its repeated full scan. The measurements below compare implementations
on a **synthetic domain**, not negotiation quality or the paper's experiments.

## Reproduce the measurement

From an installed source checkout:

```bash
python benchmarks/compare_models.py --rounds 50 100 200 --repeats 3 \
  --output outputs/model-benchmark.json
```

The script uses three issues with four values each (64 possible outcomes), equal
issue weights, and independent pseudorandom offer sequences with seeds 0, 1 and
2. It compares every observation prefix, including inferred issue/value orders
and numerical weights. Timers cover model updates; assertions are outside those
timers. A separate run records Python allocations with `tracemalloc`.

The baseline is the unchanged public NegoLog V2 CBOM source, loaded with minimal
test-only preference adapters. It is not a benchmark of NegoLog's complete
framework, logging or UI. The source hash is checked in the tests, and an
additional check against the actual installed NegoLog implementation matched
2,000 observation prefixes across 20 synthetic traces.

## Recorded local result

Measured 2026-09-09 on macOS / Apple Silicon, Python 3.10.20. Medians across the
three seeds, for the **whole sequence** of updates:

These recorded timings belong to the initial 1.0.0 implementation. Patch 1.0.1
preserves the model's inference rules; it fixes reservation filtering, protocol
state and invalid-input handling. The timings are not a new benchmark of that
patch release.

| Received offers | Reference time | Aggregated time | Ratio of median times |
| --- | --- | --- | --- |
| 50 | 0.0174 s | 0.00288 s | 6.1× |
| 100 | 0.1379 s | 0.00850 s | 16.2× |
| 200 | 1.0782 s | 0.02065 s | 52.2× |

At 200 offers, the separate allocation measurement recorded 5,939,327 bytes for
the reference and 79,148 bytes for the aggregated model. These are traced Python
allocation peaks, not total process memory. The trace/domain allocations created
before tracing are excluded for both implementations. Every measured prefix
matched the reference.

The [raw timing and allocation record](../benchmarks/results/model-comparison.json)
contains platform/interpreter metadata, each seed's result and occupied counter
counts. The [actual-framework comparison record](../benchmarks/results/actual-negolog-equivalence.json)
identifies the public model commit and comparison count. Timing varies by machine,
load, Python version, domain and offer diversity. Three seeds on one machine
do not establish a universal speedup or a statistical performance ranking.

## What scales, and what remains bounded

| Component | Behavior |
| --- | --- |
| Profile construction | Stores issues and values; never enumerates outcomes |
| CBOM update | Stores counts of observed value transitions and paired issue transitions |
| Earlier offers for new comparisons | Default maximum 1000, with repeated offers grouped by multiplicity |
| Accumulated evidence | Persists beyond the offer window; occupied counter types are bounded by the domain |
| Exact candidate search | Materializes up to 50,000 outcomes by default |
| Sampled candidate search | At most 4096 unique candidates by default; approximate strategy selection |

Tests construct a `10^20`-outcome domain with a bounded 128-candidate pool and
verify deterministic sampling without changing the global RNG. Many-issue agent
opening tests also cover 10, 20 and 100 issues at reservation utility 1. These
are construction/decision checks, not large-domain negotiation benchmarks.

The finite-domain counter bound can still be large for many issues or many
values per issue. Counters and agent histories also require storage, and integer
counts grow with observations. Consult the [cost expression](method.md#cost-and-practical-limits)
before choosing large profiles or long sessions. Bounded sampled selection does
not guarantee the exhaustive best offer, a true Nash solution or agreement.

## Correctness checks

```bash
python -m pytest
```

The suite checks random and adversarial histories, repeated offers, tied weights,
cyclic evidence, single- and multi-issue history expiration beyond 1000 offers,
profile validation, utility roundoff, literal band expansion, model-driven agent
decisions, historical-floor acceptance, reservations, terminal states, sampled
pool exhaustion, reproducible CLI traces and malformed input errors.

No human participant records or original tournament datasets are included.
