"""Test suite for the tally of the verdicts the feedback dataset records (#1150).

The deterministic suppression layer the command replayed was deleted with the model verifier,
so it counts the recorded verdicts, for each labeller, and replays nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.prompt_eval import PromptEvalBenchmarkResult, evaluate_persona_prompts
from devops_cli.commands.ai import app as ai_app
from devops_cli.exceptions import SecurityError

runner = CliRunner()


def _dataset(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    """Write a feedback dataset in the JSONL shape the review loop appends."""
    path = tmp_path / "feedback.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def _record(title: str, status: str, location: str = "src/devops_cli/core/repo.py:1") -> dict:
    """Shape one recorded finding."""
    return {
        "title": title,
        "status": status,
        "location": location,
        "description": "",
        "severity": "HIGH",
        "persona": "devsecops",
    }


# =============================================================================
# Reporting a measurement rather than a constant
# =============================================================================


def test_the_result_reports_no_figure_it_did_not_measure() -> None:
    """The command once reported accuracy 1.0 and a 0.0 false positive rate on every run, and
    then a catch rate of a layer that no longer exists: it reports the recorded counts alone."""
    fields = set(PromptEvalBenchmarkResult.model_fields)
    assert {
        "accuracy_score",
        "false_positive_rate",
        "caught_invalidations",
        "contested_verifications",
    } & fields == set()


def test_recorded_verdicts_are_counted_by_status(tmp_path: Path) -> None:
    """INVALIDATED and VERIFIED verdicts are counted; an UNVERIFIED record is a case of neither."""
    dataset = _dataset(
        tmp_path,
        [
            _record("Path.resolve() raises FileNotFoundError", "INVALIDATED"),
            _record("A genuine unbounded write", "VERIFIED"),
            _record("Not yet judged", "UNVERIFIED"),
        ],
    )
    result = evaluate_persona_prompts("devsecops", dataset_path=dataset)
    assert (result.total_cases, result.labelled_invalidated, result.labelled_verified) == (3, 1, 1)


# =============================================================================
# Reading the dataset
# =============================================================================


def test_an_absent_dataset_measures_nothing_rather_than_inventing_cases(tmp_path: Path) -> None:
    """Four hardcoded baseline pairs stood in for a missing dataset.

    A measurement over invented records describes nothing, and reporting it beside a real
    one makes the two indistinguishable.
    """
    result = evaluate_persona_prompts("devsecops", dataset_path=tmp_path / "absent.jsonl")
    assert result.total_cases == 0


def test_an_unparseable_line_is_skipped_rather_than_aborting(tmp_path: Path) -> None:
    """One bad append must not discard every record written before it."""
    path = tmp_path / "feedback.jsonl"
    path.write_text(
        "not json at all\n" + json.dumps(_record("A finding", "VERIFIED")) + "\n",
        encoding="utf-8",
    )
    assert evaluate_persona_prompts("devsecops", dataset_path=path).total_cases == 1


def test_records_for_another_persona_are_excluded(tmp_path: Path) -> None:
    """A per-persona measurement that mixed personas would not be per-persona."""
    dataset = _dataset(
        tmp_path,
        [_record("A finding", "VERIFIED"), {**_record("Other", "VERIFIED"), "persona": "qa"}],
    )
    assert evaluate_persona_prompts("devsecops", dataset_path=dataset).total_cases == 1


def test_an_oversized_dataset_is_refused(tmp_path: Path) -> None:
    """Reading an unbounded file into memory is not a measurement worth crashing for."""
    dataset = _dataset(tmp_path, [_record("A finding", "VERIFIED")])
    with patch("devops_cli.ai.prompt_eval._MAX_DATASET_BYTES", 1):
        assert evaluate_persona_prompts("devsecops", dataset_path=dataset).total_cases == 0


def test_a_symlinked_dataset_is_refused(tmp_path: Path) -> None:
    """A symlink can point anywhere; the path checks exist to stop that."""
    real = _dataset(tmp_path, [_record("A finding", "VERIFIED")])
    link = tmp_path / "linked.jsonl"
    link.symlink_to(real)
    with pytest.raises(SecurityError):
        evaluate_persona_prompts("devsecops", dataset_path=link)


# =============================================================================
# Command surface
# =============================================================================


def test_the_dry_run_reports_its_plan_without_measuring() -> None:
    """A preview reads no dataset."""
    result = runner.invoke(ai_app, ["prompt-eval", "--dry-run"])
    assert (result.exit_code, "BENCHMARK_DRY_RUN" in result.output) == (0, True)


def test_the_json_output_carries_the_counts(tmp_path: Path) -> None:
    """A consumer reads the same counts the table reports."""
    dataset = _dataset(tmp_path, [_record("A finding", "VERIFIED")])
    result = runner.invoke(ai_app, ["prompt-eval", "--json", "--dataset", str(dataset)])
    payload = json.loads(result.stdout)
    assert (result.exit_code, payload["labelled_verified"], payload["by_labeller"]) == (
        0,
        1,
        {"unknown": {"invalidated": 0, "verified": 1}},
    )


def test_a_dataset_outside_the_repository_is_refused() -> None:
    """The path is attacker-influenceable through a flag; traversal must not resolve."""
    with pytest.raises(SecurityError):
        evaluate_persona_prompts("devsecops", dataset_path=Path("/etc/passwd"))


# =============================================================================
# Counting only labels a deterministic check did not write (#950)
# =============================================================================


def _labelled(title: str, status: str, verified_by: str) -> dict[str, Any]:
    return {**_record(title, status), "verified_by": verified_by}


def test_a_deterministic_label_is_counted_as_excluded(tmp_path: Path) -> None:
    """A `deterministic:*` label is a machine's, not a person's: 28 of the 51 labels in this
    repository's dataset were such, and none was a person's."""
    dataset = _dataset(
        tmp_path,
        [_labelled("Path.resolve() raises FileNotFoundError", "INVALIDATED", "deterministic:x")],
    )

    result = evaluate_persona_prompts("devsecops", dataset_path=dataset).to_dict()

    assert (result["total_cases"], result["excluded_labels"], result["labelled_invalidated"]) == (
        0,
        {"deterministic:x": 1},
        0,
    )


def test_the_counts_are_reported_per_labeller(tmp_path: Path) -> None:
    """A person's labels, an agent's and a model's are not interchangeable ground truth."""
    dataset = _dataset(
        tmp_path,
        [
            _labelled("Path.resolve() raises FileNotFoundError", "INVALIDATED", "human"),
            _labelled("Path.resolve() raises FileNotFoundError", "VERIFIED", "llm"),
            _labelled("A defect no mechanical check decides", "INVALIDATED", "llm"),
            {**_record("A defect no mechanical check decides", "INVALIDATED")},
        ],
    )

    result = evaluate_persona_prompts("devsecops", dataset_path=dataset).to_dict()

    assert result["by_labeller"] == {
        "human": {"invalidated": 1, "verified": 0},
        "llm": {"invalidated": 1, "verified": 1},
        "unknown": {"invalidated": 1, "verified": 0},
    }


def test_deterministic_labels_are_counted_when_asked_for(tmp_path: Path) -> None:
    """Including them is a choice the reader makes, not the default."""
    dataset = _dataset(
        tmp_path,
        [_labelled("Path.resolve() raises FileNotFoundError", "INVALIDATED", "deterministic:x")],
    )

    result = runner.invoke(
        ai_app, ["prompt-eval", "--json", "--include-deterministic", "--dataset", str(dataset)]
    )
    payload = json.loads(result.stdout)

    assert (result.exit_code, payload["total_cases"], payload["excluded_labels"]) == (0, 1, {})
