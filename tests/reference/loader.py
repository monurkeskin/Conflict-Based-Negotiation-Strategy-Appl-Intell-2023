"""Execute the unchanged public algorithm with a minimal preference adapter.

Only imports of the NegoLog framework are replaced. No algorithm AST is changed.
This keeps the normal test suite independent of NegoLog's scientific/UI stack.
"""

import ast
from pathlib import Path
from types import SimpleNamespace


class Issue(str):
    """String-compatible key, like the public nenv.Issue equality/hash contract."""

    def __new__(cls, name, values):
        result = super().__new__(cls, name)
        result.name = name
        result.values = list(values)
        return result


class Base:
    def __init__(self, reference, mode="cbom"):
        assert mode == "cbom"
        issues = [Issue(i, reference.domain[i]) for i in reference.issues]
        weights = {i: 1 - reference.issue_weights[i] for i in issues}
        total = sum(weights.values())
        weights = {i: w / total if total else 1 / len(issues) for i, w in weights.items()}
        values = {i: {v: 1 - reference.value_weights[i][v] for v in i.values} for i in issues}
        for vals in values.values():
            maximum = max(vals.values())
            for value in vals:
                vals[value] = vals[value] / maximum if maximum else 1.0
        self._pref = SimpleNamespace(issues=issues, _issue_weights=weights, _value_weights=values)

    @property
    def preference(self):
        return self._pref


def load_reference():
    path = Path(__file__).with_name("negolog_v2_cbom.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and node.module.startswith("nenv.")
    )]
    namespace = {"AbstractOpponentModel": Base, "Preference": object, "Bid": dict}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace["ConflictBasedOpponentModel"]
