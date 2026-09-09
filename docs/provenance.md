# Sources, attribution and reproducibility

This repository connects the CBOM opponent model to the negotiation strategy
associated with the following paper:

**Mehmet Onur Keskin, Berk Buzcu and Reyhan Aydoğan.**
“Conflict-based negotiation strategy for human-agent negotiation.”
*Applied Intelligence* **53**, 29741–29757 (2023).
[DOI: 10.1007/s10489-023-05001-9](https://doi.org/10.1007/s10489-023-05001-9).

The publisher records online publication on 3 November 2023. Use this article
when citing the CBOM method, and the software version used when reporting
experiments with this maintained implementation.

## Source register

| Source | Exact version | What it establishes |
| --- | --- | --- |
| [Published article](https://link.springer.com/article/10.1007/s10489-023-05001-9) | Applied Intelligence 53, 29741–29757; published 2023-11-03 | Method, negotiation strategy and the experiments reported by the authors. |
| [CBOM model in NegoLog V2](https://github.com/monurkeskin/NegoLogV2/blob/c13b4f791db9ba682e451d90baa3bc3e0bdf6052/nenv/OpponentModel/ConflictBasedOpponentModel.py) | Commit `c13b4f791db9ba682e451d90baa3bc3e0bdf6052`, release `v2.0.0` | Reference for current model behavior: accumulated evidence, majority comparisons, ties, rank weights and the 1000-offer comparison horizon. |
| [CBOM preference initialization in NegoLog V2](https://github.com/monurkeskin/NegoLogV2/blob/c13b4f791db9ba682e451d90baa3bc3e0bdf6052/nenv/OpponentModel/CBOMEstimatedPreference.py) | Same commit | Inverse own-preference initialization. |
| Berk Buzcu's historical negotiation-strategy prototype | Historical GPL-3.0 precursor inspected as implementation context | Earlier strategy design and implementation pitfalls. It does not implement the published Algorithm 2 completely and is not an exact paper-reproduction reference. |
| [Public Hybrid strategy implementation](https://github.com/berkbuzcu/HumanRobotNego/blob/0a2dd11ad324a057e7af9d2cd1cdccbf4c7bf499/human_robot_negotiation/agent/solver_agent/solver_agent/solver_agent.py) | Commit `0a2dd11ad324a057e7af9d2cd1cdccbf4c7bf499` | Implementation context for Hybrid concession parameters and recent-difference weights. Other features of that project are separate from the CBOM method. |
| This repository's tests and example runs | Record the checked-out commit and run configuration | Current implementation behavior, model equivalence checks and measured software performance for the tested inputs. |

The published PDF used for the method review has SHA-256
`55c3a47c3892702d872b28ded1321321a41974ce24945d72d89317c40a6bd745`.
This identifies the reviewed publisher artifact without requiring a local
filesystem layout.

## Where to find the method in the paper

| Topic | Published location |
| --- | --- |
| Additive utility and discrete issues | Section 3, Equation 1, p. 29743 |
| Concession assumption; inverse or arbitrary initial ordering | Section 3, p. 29744 |
| Value-rank normalization and recursive issue weights | Equations 2–3, p. 29744 |
| Value conflicts and issue conflicts | Figure 1 and accompanying text, pp. 29744–29745 |
| Persistent comparison map and majority updates | Algorithm 1, p. 29745 |
| Hybrid target, candidate offers, product objective and acceptance | Section 4, Algorithm 2 and Equations 4–8, pp. 29745–29747 |
| Evaluation protocol | Section 5, pp. 29747–29753 |
| Computational limitations | Section 6, p. 29753; Appendix Table 9, p. 29755 |

## What changed

The model replaces explicit stored offer comparisons with cumulative transition
counters. Its counters preserve the contribution of repeated observations and
allow historical comparisons to be reinterpreted when beliefs change. The
equivalence argument and complexity bounds are documented in
[method.md](method.md#why-aggregation-preserves-the-model).

The comparison reference is the pinned public NegoLog V2 model, not a claim of
bit-for-bit identity with the 2023 experiment code. In particular:

- The current model uses normalized issue ranks; the paper prints a different
  recursive issue-weight formula.
- By default, new comparisons use the previous 1000 offers, while older
  accumulated evidence remains. The paper describes all-history comparisons.
- Pairwise-majority ties and cycles need an operational sorting policy; the
  maintained implementation follows the public reference's deterministic
  behavior.
- Strategy startup, search exhaustion and incompletely specified parameters
  require explicit implementation choices.

The historical strategy prototype was reviewed before reconstructing the
published offering and acceptance algorithm. Its incomplete model integration,
different concession controls and differing acceptance logic are not treated as
the specification of the 2023 paper. The published algorithm supplies that
specification; explicitly documented implementation choices fill its gaps.

Report these choices, the repository commit, profile definitions, history limit
and strategy settings when publishing an experiment using this code.

## What the evidence supports

The article reports human-agent and automated-negotiation experiments. Those
findings belong to the article and its protocol. This repository does not
redistribute the original participant records or establish a new replication of
those findings.

Software tests can establish that the implementation handles specified inputs,
that its strategy consumes the updated model, and that its outputs match a
reference on tested traces. Benchmarks can measure time and storage for specified
synthetic domains and histories. Neither alone establishes superior negotiation
utility, better human interaction or a new state-of-the-art result.

## Credit and licensing

The research method is credited to Mehmet Onur Keskin, Berk Buzcu and Reyhan
Aydoğan. The historical strategy work is credited to Berk Buzcu and the paper's
authors. The maintained model derives from NegoLog V2's public CBOM
implementation; source attribution and licensing are recorded in the repository
license and notices.

The article itself is published under Creative Commons Attribution 4.0, as
recorded on p. 29755. The article's license and the software license are separate.
Use [the publisher's article](https://doi.org/10.1007/s10489-023-05001-9) for the
authoritative paper and [the CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/)
for its reuse terms. Cite the paper for the method and retain applicable software
notices when redistributing code.
