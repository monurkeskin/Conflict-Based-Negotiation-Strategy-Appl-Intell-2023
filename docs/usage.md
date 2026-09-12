# Use CBOM in your project

[Back to README](../README.md) · [Method and settings](method.md) · [Performance](performance.md)

For the native Java API or CLI, see [the Java guide](../java/README.md).
For ready-to-run Python/Java agents inside NegoLog, see [framework integration](negolog.md).

## Define your domain

A domain contains discrete issues, each with possible string values. A profile
adds your utility for each value, an importance weight for each issue and a
reservation utility. Utilities use a weighted sum; issue weights must sum to one.

```json
{
  "reservationValue": 0.3,
  "issueWeights": {"delivery": 0.6, "support": 0.4},
  "issues": {
    "delivery": {"this_week": 1.0, "next_week": 0.5},
    "support": {"premium": 1.0, "standard": 0.0}
  }
}
```

The bid `{"delivery": "next_week", "support": "premium"}` has utility
`0.6 × 0.5 + 0.4 × 1.0 = 0.7`. Both parties share issue names and available values
but can assign different utilities and weights. Values and reservation utility
must lie in `[0, 1]`; each issue needs at least one value. Preserve domain order
for reproducible tie breaking. The JSON schema is compatible with NegoLog profiles.

Save profiles as UTF-8 JSON. The [example profiles](../examples) illustrate a
27-outcome domain. No list of all outcomes is required in a profile.

## Run a negotiation

After the [README installation](../README.md#run-your-first-negotiation):

```bash
cbom demo --profile-a examples/profile_a.json --profile-b examples/profile_b.json \
  --rounds 30 --seed 0 --output outputs/custom-demo.json
```

`rounds` allows up to twice that many alternating actions, including acceptance
or ending. Time runs from zero to one across those turns. This is a minimal local
runner; use your negotiation framework for tournaments, external parties or
human-facing interfaces.

The JSON output contains profiles, settings, outcome, agreement utilities and a
`trace` array. Each row records:

| Field | Meaning |
| --- | --- |
| `agent`, `turn`, `time` | Acting party, one-based action count and normalized time |
| `kind`, `bid` | `offer`, `accept` or `end`, plus the relevant bid when present |
| `own_utility`, `target` | Utility of the action's bid and the strategy's target when applicable |
| `model_observations` | Opponent offers incorporated before this decision |
| `selection` | Candidate-search details, or `null` when no search result applies |
| `selection.opponent_utility` | Estimated utility used for product scoring; `null` before warmup |
| `selection.epsilon` | Final half-width of the utility band |
| `selection.candidate_count` | Eligible candidates inside that band |
| `selection.exact` | Whether the pool enumerates the whole outcome space |

Keep the output and your repository commit when comparing runs. Agreement
utilities are computed from the synthetic profiles, not from a learned ground
truth or a human participant's unobserved preferences.

## Integrate the agent

```python
from cbom import Preference
from cbom.strategy import CBOMAgent

own = Preference.from_json("examples/profile_a.json")
agent = CBOMAgent(own, model_threshold=3, mode="auto", seed=0)

opening = agent.act(0.0)
print(opening.kind, opening.bid)

received = {"delivery": "next_month", "support": "self_service", "payment": "upfront"}
agent.receive(received, t=0.1)
response = agent.act(0.1)
print(response.kind, response.bid)
```

Call `receive()` once for each actual opponent offer; it updates the same model
used by `act()`. Call `act()` to make the agent's next decision. Times must be
finite, nondecreasing and in `[0, 1]`. Start a new agent for each new session.
An `accept` action refers to the latest received offer; an `end` action closes
the session without agreement.

Sending a counteroffer declines that received offer. A later `act()` call can
produce another proposal, but it cannot accept the declined offer unless the
opponent sends it again. Normal alternating sessions call `receive()` before
each response; the local demo follows that protocol.

Before three opponent offers, candidate selection maximizes own utility. From
the third offer onward, it maximizes own utility × CBOM's estimated opponent
utility. The model still learns during warmup. Configure a different warmup with
`model_threshold`; its default is an implementation choice, not a recovered
paper experiment setting.

The initial offer maximizes own utility. Later targets blend the time-based
concession curve with recent opponent concessions. Acceptance follows the
paper's minimum across prior own offers and the next candidate, with an added
reservation floor. [The method guide](method.md#offering-and-acceptance-strategy)
defines the equations and complete defaults.

## Choose a search mode

| Setting | Behavior | Use when |
| --- | --- | --- |
| `mode="auto"` | Exact up to 50,000 outcomes; seeded sample above that | You want bounded default behavior |
| `mode="exact"` | Full domain, rejected if above `max_exact_outcomes` | You need exhaustive candidate selection |
| `mode="sampled"` | Fixed pool of at most `sample_size` unique bids, including own maximum | You explicitly accept approximate candidate selection |

```python
agent = CBOMAgent(own, mode="sampled", sample_size=8192, seed=42)
```

Sampling changes the strategy's available candidates; **it does not approximate
the CBOM model update**. The sampled pool is created once. Its best candidate
need not be the best in the full domain, and it can run out of unused bids even
when the full domain has more outcomes. Larger samples trade memory and time for
broader coverage. The seed is local and does not alter Python's global RNG.

The utility band expands by `0.01` until an unused candidate is found. If no
eligible unused bid remains, the agent accepts an admissible latest offer or
ends. It also ends at the deadline if no latest offer meets its acceptance rule.
These termination rules resolve cases left open by the paper's pseudocode.

## Use only the estimator

```python
from cbom import ConflictBasedOpponentModel

model = ConflictBasedOpponentModel(own, history_size=1000)
model.update(received)
estimated_profile = model.preference
estimated_utility = estimated_profile.utility(received)
```

`model.preference` returns the latest estimated profile. A previously saved
profile remains a snapshot after later updates. `model.observations` counts
received offers, `model.comparisons` counts nonidentical chronological offer
pairs, and `model.evidence_cells` counts occupied aggregated evidence counters.
`model.value_ordering` and `model.issue_ordering` list ranks from least to most
preferred; treat these diagnostic lists as read-only.

`history_size` limits the earlier offers used to create **new** comparisons.
Existing evidence remains accumulated. Changing this setting changes the model;
it is not merely a memory option. Refer to [history semantics](method.md#history-and-ties).

For a file, place one complete JSON bid on each line:

```bash
cbom learn --profile examples/profile_a.json --offers examples/offers.jsonl \
  --history-size 1000 --output outputs/estimated-profile.json
```

The command reports invalid offer line numbers. Empty lines are allowed.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `cbom: command not found` | Activate the environment, install the package, or run `python -m cbom` |
| Unsupported Python version | Create the environment with Python 3.10 or newer |
| `Issue weights must sum to one` | Normalize importance weights; value utilities are separate |
| Unknown value or incomplete bid | Match profile issue/value strings exactly and supply all issues |
| Exact search exceeds the limit | Choose sampled mode or explicitly raise `max_exact_outcomes` after assessing domain size |
| Session ends after very few offers | Inspect reservation values, available bids, sample size and trace fields |
| Estimates differ from a paper table | This release has documented model/formula and setting differences; examples do not replay the original experiments |
| Estimated utility is not an acceptance probability | CBOM estimates an ordinally derived utility function, not a classifier |

For a reproducible bug report, include version, Python version, a minimal
synthetic profile, offer sequence, settings and the traceback. Use the
[issue tracker](https://github.com/monurkeskin/Conflict-Based-Negotiation-Strategy-Appl-Intell-2023/issues).
