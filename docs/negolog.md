# Run CBOM in NegoLog

[Back to README](../README.md) · [Java guide](../java/README.md) · [Method](method.md)

Use the standalone CBOM package for a minimal negotiation or model API. Use
NegoLog when you want tournaments, baseline agents, Excel logs and its local web
interface. The CBOM opponent model is part of the bidding agent in both routes.

![A shared CBOM strategy has Python and Java implementations, usable alone or through NegoLog adapters.](assets/integrations.svg)

## Choose your starting point

| Task | Repository and command |
| --- | --- |
| Minimal Python negotiation | This repository: `cbom demo --output outputs/python.json` |
| Minimal Java negotiation | This repository: `python java/build.py`, then `java -jar java/build/cbom.jar demo --output outputs/java.json` |
| Python CBOM against an existing agent | NegoLog V2: `python run.py tournament_configurations/cbom-python.yaml` |
| Compare Python CBOM, Java CBOM and Boulware | NegoLog V2: build the bundled Java agent, then run `tournament_configurations/cbom.yaml` |

The maintained [NegoLog V2 repository](https://github.com/monurkeskin/NegoLogV2)
and the [upstream NegoLog repository](https://github.com/aniltrue/NegoLog) host the
framework integration. Use a revision containing `agents/CBOM/`; each includes
its own copy of the public core. A neighboring CBOM clone is not required.
Check the upstream branch or PR when a new integration is still under review.

## Run a complete framework comparison

First install the framework following its README; NegoLog's current dependency
constraints target **Python 3.10**. From that checkout's root:

```bash
# Two sessions: Python CBOM and Boulware, swapping roles. No JDK required.
python run.py tournament_configurations/cbom-python.yaml

# Optional: enable the genuine Java implementation (JDK 17 or newer).
java -version
javac -version
python agents/CBOM/java/build.py

# Six sessions: Python CBOM, Java CBOM and Boulware, in both role orders.
python run.py tournament_configurations/cbom.yaml
```

Inspect `results/cbom/results.xlsx`, `summary.xlsx` and the session workbooks.
The display names are `CBOM` and `CBOMJava`; the YAML class names are `CBOMAgent`
and `CBOMJavaAgent`. A valid run may end without agreement. Each configured
result directory is replaced when rerun; change it to retain previous results.

For one session with less output:

```bash
python examples/cbom_session.py --agent-a python --agent-b java --domain 0 \
  --rounds 30 --output results/cbom-session.xlsx
```

NegoLog remains a Python framework. Selecting `CBOMJavaAgent` starts a persistent
Java process that owns the model and makes the decisions. Its adapter translates
profiles, offers and actions; it does not call the Python strategy to decide.
Build Java before the timed session, and create a fresh agent per session.

## Understand what is shared

Both implementations use the documented Hybrid concession, CBOM updates,
candidate band, product selection and historical acceptance floor. Both return
offer, accept or end. The framework records a voluntary end as a no-agreement
result with an explicit reason, rather than treating it as an agent exception.

The Python core is the same public source used by this package. Java is a native
port. Language-parity tests check complete decisions and learned preferences on
deterministic traces; read the [Java guide](../java/README.md) for the pinned
CPython 3.10 sorting rule on cyclic rankings. Use Python 3.10 for cross-language
comparisons; newer Python versions can differ even on short cyclic rankings.
Do not infer unrestricted bitwise equivalence from matching examples.

Exact and sampled search keep the same meaning as in [usage.md](usage.md).
The standalone model avoids outcome enumeration, but NegoLog itself can enumerate
bids for its domain loader or evaluation loggers. Using a sampled CBOM agent does
not remove those framework costs.

## Cite the method and framework

When using the CBOM strategy, cite [Keskin, Buzcu and Aydoğan (2023)](https://doi.org/10.1007/s10489-023-05001-9).
When NegoLog runs or assesses the experiment, also cite
[Doğru et al. (2024)](https://doi.org/10.24963/ijcai.2024/998).
Record both software revisions, language, search mode, seed, profiles and
deadlines. The bundled examples are synthetic usability checks.

## Maintain the bundled sources

The framework adapters are maintained in NegoLog. To refresh their public CBOM
core after a reviewed CBOM change, run from this checkout:

```bash
python tools/sync_negolog.py ../NegoLogV2
python tools/sync_negolog.py ../NegoLogV2 --check
```

The tool copies explicit Python/Java source and attribution files and writes
`agents/CBOM/vendor-manifest.json` with SHA-256 hashes. It leaves the adapter
and generated build output alone. Rebuild the JAR and run both repositories'
tests before committing a refreshed copy.
