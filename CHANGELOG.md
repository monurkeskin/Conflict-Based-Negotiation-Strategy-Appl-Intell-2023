# Changelog

## 1.0.1 — 2026-09-09

- Apply the reservation floor consistently in search and agent decisions.
  A candidate just below reservation no longer hides a feasible offer and ends
  the session prematurely; utility-band tolerance is retained.
- Expire a received offer when counteroffering, preventing a later `act()` call
  from accepting a previously declined offer without a new `receive()` event.
- Report oversized JSON integers and malformed search modes as input errors.
- Extend regression and end-to-end checks for boundary profiles and protocol state.

## 1.0.0 — 2026-09-09

- Standalone, dependency-free CBOM model with cumulative transition counters.
- Differential validation against the frozen finalized NegoLog V2 model.
- Published Algorithm 2 offering/acceptance strategy consuming live CBOM updates.
- Validated additive profiles, exact and bounded sampled candidate search,
  reservation guards, deadline and candidate-exhaustion handling.
- Local negotiation and model-learning CLI, synthetic examples and JSON traces.
- Method differences, source attribution, citation metadata and measured
  implementation-performance report.

This is the first release of this standalone repository. Its version does not
rename the 2023 article or identify an original experiment artifact.
