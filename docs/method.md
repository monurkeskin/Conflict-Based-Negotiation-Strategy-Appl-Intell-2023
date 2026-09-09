# Method and implementation choices

CBOM estimates an opponent's preferences from the offers they make. The agent
uses that estimate to choose among offers near its own target utility. These are
separate components: the model learns preferences; the strategy decides what to
offer and whether to accept.

This repository maintains the method associated with [Keskin, Buzcu and Aydoğan
(2023)](https://doi.org/10.1007/s10489-023-05001-9). Its model follows the public
[NegoLog V2 implementation at `c13b4f7`](https://github.com/monurkeskin/NegoLogV2/blob/c13b4f791db9ba682e451d90baa3bc3e0bdf6052/nenv/OpponentModel/ConflictBasedOpponentModel.py),
with an exact aggregation of that implementation's comparison evidence.
Some numerical and operational choices differ from the published paper. This is
a maintained implementation, and running its examples does not reproduce the
paper's human studies or tournament results.

## Preference model

Offers assign one discrete value to every issue. Utilities are additive:

$$
U(o)=\sum_{i=1}^{I}w_i V_i(o_i),\qquad \sum_i w_i=1.
$$

This is Equation 1 of the paper, p. 29743. CBOM first estimates an ordering of
values within each issue and an ordering of issues by importance. Higher ranks
mean more preferred values or more important issues.

The model assumes that earlier opponent offers are generally preferred by the
opponent to later offers: the opponent concedes over time. This is an inference
assumption, not a guarantee about human or automated behavior. The initial
ordering is the inverse of the agent's own issue and value weights, one of the
initialization choices discussed on p. 29744. Equal initial weights are ordered
in reverse domain input order, preserving NegoLog V2's tie behavior.

### Evidence from offers

For each newly received offer, compare it with earlier offers:

1. **One changed issue:** count evidence that the earlier value is preferred to
   the later value.
2. **Several changed issues:** use the current value ordering to identify losses
   and gains for the opponent. For every loss/gain issue pair, count evidence
   that the loss issue is more important than the gain issue.
3. Compare evidence in the two directions for each value or issue pair. Retain
   the previous ordering on equal counts, then update the numerical utility
   estimate.

The two conflict types appear in Figure 1, pp. 29744–29745; the update procedure
is Algorithm 1, p. 29745. Loss/gain inference is a heuristic based on concession
and ordinal preferences. It does not uniquely identify a true additive utility
function or prove every inferred importance relation.

As in the public reference implementation, issue evidence is evaluated using the
value ordering **before** this observation's value-order update. Previously
stored evidence is reconsidered after each observation, because changed beliefs
can change its interpretation.

### Numerical weights

For a value of rank $r$ in an issue with $m$ values:

$$V(v)=r/m,\qquad r\in\{1,\ldots,m\}.$$

This matches Equation 2, p. 29744. For an issue of rank $r$ among $I$ issues, the
maintained implementation uses:

$$w_i=\frac{r}{I(I+1)/2}.$$

This positive, normalized rank weighting is the public NegoLog V2 behavior.
**It differs from Equation 3 of the paper**, which describes a recursive
weighting anchored at the middle issue. Accordingly, an identical ordinal
ordering need not produce the same numerical utilities as the historical
paper implementation.

### History and ties

The default `history_size=1000` determines which earlier offers are compared
with a new offer. Existing evidence remains accumulated when an offer leaves
that window. This preserves the public NegoLog V2 default; the paper describes
comparisons with all earlier offers without this limit. Changing `history_size`
changes the model's evidence and should be reported when comparing experiments.

Identical offer pairs add no evidence, but repeated offers are not discarded:
each occurrence contributes its multiplicity when compared with a different
offer. Pairwise majorities can be cyclic. The deterministic sorting procedure
preserves the reference implementation's ordering policy; it is not a global
minimum-conflict ranking algorithm. Domain input order and prior beliefs can
therefore matter when evidence is tied or cyclic.

## Why aggregation preserves the model

The reference stores a comparison map containing the differing values for every
eligible chronological offer pair, and rescans that map on every update. The
maintained implementation stores sufficient counts for exactly those operations.

Let $d_i=(i,a,b)$ denote a change from old value $a$ to new value $b$ on issue
$i$, with $a\ne b$.

- A comparison with exactly one changed issue increments the counter $S(d_i)$.
- A comparison with several changed issues increments a counter $J(d_i,d_j)$
  for each unordered pair of changed issues $i<j$.
- Repeated earlier offers are grouped by content with their occurrence count;
  every increment is multiplied by that count.

At the next belief update, $S(i,a,b)$ is precisely the reference's count of
single-issue evidence for $a$ over $b$. For issue evidence, let $L_B(d_i)$ be
true when the old value is preferred to the new value under the pre-update
belief $B$. Then:

$$
C_B(i,j)=\sum_{d_i,d_j}J(d_i,d_j)
\mathbf{1}\{L_B(d_i)\land\neg L_B(d_j)\}.
$$

The reversed orientation contributes to $C_B(j,i)$. A comparison in the reference
contributes once for each loss/gain issue pair. Splitting it into unordered
issue-pair records makes exactly the same contributions, including comparisons
that change three or more issues. Summing equal records changes storage, not
their multiplicity. Re-evaluating them under the current pre-update belief
preserves reinterpretation of historical evidence.

Consequently, if the domain order, initial beliefs, history limit and observation
sequence match, the evidence counts at each update match. Applying the same
majority comparisons, tie policy and numerical rank mappings gives the same
next preferences. This is an equivalence argument for the pinned public model,
not for every possible interpretation of the paper's pseudocode. Differential
tests are the executable check of this argument.

### Cost and practical limits

Let $H$ be the history limit, $U\le H$ the number of distinct offers currently in
that history, $m_i$ the number of values for issue $i$, and
$D_i=m_i(m_i-1)$ the number of directed value transitions. The maximum number of
evidence-counter keys is:

$$K\le\sum_i D_i+\sum_{i<j}D_iD_j.$$

This bound depends on the domain, rather than the number of received offers.
The actual implementation stores only occupied counters. With constant-time
dictionary operations, one update costs

$$
O\!\left(UI^2+K_{\rm joint}+\sum_i m_i\log m_i+I\log I\right),
$$

where $K_{\rm joint}$ counts occupied joint-transition counters. The number of
stored objects is $O(HI+K+\sum_i m_i)$. Counter integers still grow as observations
accumulate; their bit size is not strictly constant for an unbounded session.

The model does not enumerate the Cartesian product of outcomes. Many issues or
many values per issue can nevertheless make the joint-transition table large.
Offer selection has its own search cost, independent of the model update cost.
Performance measurements on included synthetic examples should be interpreted
for their stated domains and histories, not as proof of unrestricted scale or
improved negotiation outcomes.

## Offering and acceptance strategy

Section 4, pp. 29745–29747, combines CBOM with a Hybrid target utility. The
published Equations 4–8 are:

$$
\begin{aligned}
T(t)&=t^2T_{\rm time}(t)+(1-t^2)T_{\rm behavior}(t),\\
T_{\rm time}(t)&=(1-t)^2P_0+2(1-t)tP_1+t^2P_2,\\
T_{\rm behavior}(t)&=U(o^{\rm own}_{\rm previous})-\mu(t)\Delta U,\\
\Delta U&=\sum_{i=1}^{4}W_i\left[U(o^{\rm opp}_{t-i})-U(o^{\rm opp}_{t-i-1})\right],\\
\mu(t)&=P_3(1+t).
\end{aligned}
$$

Time is normalized to $[0,1]$. Positive changes in the opponent offer's utility
to the agent indicate a concession and lower the agent's behavioral target.
The paper reports $P_0=0.9$, $P_1=0.7$ and $P_2=0.4$ on p. 29746. It does not
fully specify $P_3$, the difference weights $W_i$, the initial band width, the
minimum observation count $n$, or all startup and outcome-exhaustion cases.
The implementation choices below fill these gaps; they are not recovered
experimental settings.

Algorithm 2 searches for offers in $[T-\epsilon,T+\epsilon]$ that the agent has
not previously offered. It expands the band if necessary. Before $n$ opponent
offers have arrived, it maximizes its own utility among the candidates;
afterward, it maximizes the product of its own utility and the estimated
opponent utility. This is a candidate-set product objective; it does not prove
that the chosen offer is the true global Nash bargaining solution.

The acceptance condition in Algorithm 2, line 16, is:

$$
U(o^{\rm opp}_{\rm latest})\ge
\min_{o\in O_{\rm own}\cup\{o_{\rm next}\}} U(o).
$$

This explicitly uses the minimum across historical own offers and the proposed
next offer. The surrounding prose is less precise. Two further pseudocode
details require care: its printed `while` condition tests a nonempty candidate
set although that set starts empty, and excluding every prior offer requires a
defined fallback once all outcomes have been offered. Implementations must
resolve those cases rather than copy a nonterminating or unreachable loop.

### Defaults and parameter provenance

The agent constructor is:

```python
CBOMAgent(
    preference,
    model=None,
    *,
    p0=0.9,
    p1=0.7,
    p2=0.4,
    p3=0.5,
    model_threshold=3,
    epsilon=0.02,
    mode="auto",
    max_exact_outcomes=50_000,
    sample_size=4096,
    seed=0,
)
```

| Setting | Default | Source or purpose |
| --- | --- | --- |
| `p0`, `p1`, `p2` | `0.9`, `0.7`, `0.4` | Reported in the paper, p. 29746. |
| `p3` | `0.5` | Public Hybrid strategy implementation; not specified numerically in the CBOM paper. |
| `model_threshold` | `3` observations | Engineering default for switching candidate scoring from own utility to utility product; not a reported paper setting. |
| `epsilon` | `0.02` | Engineering default for the initial utility band. Expansion increments of `0.01` follow Algorithm 2. |
| `mode` | `"auto"` | Exact candidate enumeration on smaller domains; bounded sampled search on larger domains. |
| `max_exact_outcomes` | `50_000` | Explicit maximum for exact enumeration. |
| `sample_size` | `4096` | Maximum number of unique candidate bids in sampled mode; duplicates can reduce the actual count. |
| `seed` | `0` | Local random seed for the sampled candidate pool. |

The default model uses `history_size=1000`. A model provided explicitly lets the
caller configure that horizon independently from the candidate-search settings.

For the behavioral target, use up to four consecutive opponent-utility
differences. The weights below come from the public Hybrid implementation linked
in [provenance.md](provenance.md), and are listed from oldest to newest:

| Available differences | Weights |
| --- | --- |
| 1 | `[1.0]` |
| 2 | `[0.25, 0.75]` |
| 3 | `[0.11, 0.22, 0.66]` |
| 4 | `[0.05, 0.15, 0.30, 0.50]` |

The three-difference weights sum to `0.99`. This historical numerical choice is
preserved, rather than silently renormalized. The code does not add the emotion
or sensitivity adaptation present elsewhere in that source project.

### Exact and sampled candidate search

In `"exact"` mode, the candidate pool contains every outcome. An explicit limit
prevents accidental enumeration above `max_exact_outcomes`; requesting exact
mode above that limit raises an error. In `"auto"` mode, domains with at most
50,000 outcomes are enumerated with the default settings. Larger domains use
the sampled mode instead. The domain's outcome count is computed from the issue
cardinalities without first materializing the outcome space.

Sampled mode makes a finite number of seeded draws, removes duplicate bids and
always includes the agent's own-utility maximum. The resulting pool is fixed for
the session and contains at most `sample_size` distinct bids. It does not claim
to cover every useful bid or find the global best product. Changing the seed,
sample size or mode can change the negotiation trajectory.

Both modes exclude previously offered bids and offers below the agent's
reservation utility. They find the first nonempty band on the
`epsilon + k * 0.01` grid, then maximize own utility or the estimated utility
product within that band. The implementation skips empty expansion iterations
using the nearest available utility distance. A tolerance of `1e-12` is used at
band and reservation boundaries to handle floating-point arithmetic. Tied scores
keep the first candidate in the stable utility-sorted pool.

Every `Selection` reports its `exact` flag, effective `epsilon` and
`candidate_count`. Here, **exact means complete candidate-pool enumeration**;
it does not mean the estimated opponent utility is known to be correct. Sampled
search changes the strategy's available candidates, not the model's update or
the aggregation equivalence above.

If no unused candidate at or above reservation remains, the search raises
`NoAvailableBid`. The agent ends the negotiation when no acceptable received
offer is available. A sampled pool can be exhausted even while other domain
outcomes remain unvisited. At normalized deadline `t=1`, the agent likewise
accepts an eligible received offer or ends; it does not continue an unbounded
search or emit another offer. Reservation protection and these termination
rules are explicit engineering completions of the paper's underspecified cases.

## Evidence and attribution

See [provenance.md](provenance.md) for the exact source versions and the boundary
between published findings, historical code behavior and current software
validation. This repository's examples and benchmarks are synthetic software
checks. The paper's experiments require their original data and protocol; their
results are not re-established by unit tests or example negotiations.
