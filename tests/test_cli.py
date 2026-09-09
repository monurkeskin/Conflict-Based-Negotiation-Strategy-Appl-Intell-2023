"""User-facing commands and trace invariants, including installed package data."""

import json
from importlib.resources import files

import pytest

from cbom.cli import example_profile, main, negotiate


def test_synthetic_demo_is_reproducible_and_models_drive_proposals():
    profiles = [example_profile(side) for side in "ab"]
    result = negotiate(*profiles)
    assert result == negotiate(*profiles)
    assert result["outcome"] == "agreement"
    assert result["utilities"] == pytest.approx({"A": .65, "B": .65})
    assert len(result["trace"]) == 17
    assert result["trace"][-1]["kind"] == "accept"
    assert result["trace"][-1]["bid"] == result["trace"][-2]["bid"]
    learned_choices = [row for row in result["trace"] if row["selection"]
                       and row["selection"]["opponent_utility"] is not None]
    assert learned_choices
    assert all(row["model_observations"] >= 3 for row in learned_choices)
    assert all(row["selection"]["exact"] for row in learned_choices)


def test_cli_demo_writes_self_contained_trace(tmp_path, capsys):
    output = tmp_path / "nested" / "demo.json"
    assert main(["demo", "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["profiles"]["A"] == example_profile("a").to_dict()
    assert "Outcome: agreement" in capsys.readouterr().out


def test_cli_learn_and_line_errors(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text(files("cbom").joinpath("data/profile_a.json").read_text())
    offers = tmp_path / "offers.jsonl"
    offers.write_text('\n{"delivery":"this_week","support":"premium","payment":"60_days"}\n')
    output = tmp_path / "estimate.json"
    arguments = ["learn", "--profile", str(profile), "--offers", str(offers), "--output", str(output)]
    assert main(arguments) == 0
    assert set(json.loads(output.read_text())["issueWeights"]) == {"delivery", "support", "payment"}
    offers.write_text('\n{"delivery":"unknown"}\n')
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


@pytest.mark.parametrize("arguments", [
    ["demo", "--rounds", "0"],
    ["demo", "--profile-a", "missing.json"],
    ["learn", "--profile", "missing.json", "--offers", "missing.jsonl"],
])
def test_invalid_command_input(arguments):
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_sampled_pool_exhaustion_is_visible():
    result = negotiate(example_profile("a"), example_profile("b"), mode="sampled", sample_size=1)
    assert result["outcome"] == "ended"
    assert result["trace"][-1]["reason"] == "candidate pool exhausted"
    assert result["trace"][0]["selection"]["exact"] is False


@pytest.mark.parametrize("data", [[],
    {"issueWeights": ["x"], "issues": {"x": {"a": 1}}},
    {"issueWeights": {"x": 1}, "issues": {"x": ["a"]}},
])
def test_malformed_profile_reports_input_error(tmp_path, capsys, data):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(SystemExit) as error:
        main(["learn", "--profile", str(path), "--offers", str(path)])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert "error:" in message
    assert "Traceback" not in message
