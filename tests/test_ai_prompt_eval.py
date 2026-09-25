"""Test suite for measuring the deterministic suppression layer against recorded verdicts."""

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


def test_the_result_reports_the_layers_decisions_not_the_datasets_labels() -> None:
    """The command reported accuracy 1.0 and a 0.0 false positive rate on every run.

    It counted the dataset's own labels and assigned those two constants without
    evaluating anything, so a loop measured at a 40-85% false positive rate in two
    calibration sessions was reported as flawless on 1311 cases.
    """
    fields = set(PromptEvalBenchmarkResult.model_fields)
    assert {"accuracy_score", "false_positive_rate"} & fields == set()


def test_an_invalidation_the_layer_reaches_is_counted_as_caught(tmp_path: Path) -> None:
    """Each one is a finding the model verifier never has to be asked about."""
    dataset = _dataset(
        tmp_path, [_record("Path.resolve() raises FileNotFoundError", "INVALIDATED")]
    )
    result = evaluate_persona_prompts("devsecops", dataset_path=dataset)
    assert (result.labelled_invalidated, result.caught_invalidations) == (1, 1)


def test_an_invalidation_the_layer_misses_lowers_the_catch_rate(tmp_path: Path) -> None:
    """A rate that could not fall would measure nothing."""
    dataset = _dataset(tmp_path, [_record("A defect no mechanical check decides", "INVALIDATED")])
    result = evaluate_persona_prompts("devsecops", dataset_path=dataset)
    assert (result.caught_invalidations, result.catch_rate) == (0, 0.0)


def test_a_suppressed_verification_is_reported_as_contested(tmp_path: Path) -> None:
    """This is the direction that buries real defects, so it is never netted away."""
    dataset = _dataset(tmp_path, [_record("Path.resolve() raises FileNotFoundError", "VERIFIED")])
    result = evaluate_persona_prompts("devsecops", dataset_path=dataset)
    assert (result.labelled_verified, result.contested_verifications) == (1, 1)


def test_a_verification_the_layer_leaves_alone_is_not_contested(tmp_path: Path) -> None:
    """Most verified findings must pass through untouched, or the layer is unusable."""
    dataset = _dataset(tmp_path, [_record("A genuine unbounded write", "VERIFIED")])
    result = evaluate_persona_prompts("devsecops", dataset_path=dataset)
    assert result.contested_verifications == 0


def test_the_two_rates_are_reported_separately(tmp_path: Path) -> None:
    """One accuracy figure would let a gain on either side hide a loss on the other."""
    dataset = _dataset(
        tmp_path,
        [
            _record("Path.resolve() raises FileNotFoundError", "INVALIDATED"),
            _record("Path.resolve() raises FileNotFoundError", "VERIFIED"),
        ],
    )
    result = evaluate_persona_prompts("devsecops", dataset_path=dataset).to_dict()
    assert (result["catch_rate"], result["contested_rate"]) == (1.0, 1.0)


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
    """A preview must not spend minutes replaying the layer over the whole dataset."""
    result = runner.invoke(ai_app, ["prompt-eval", "--dry-run"])
    assert (result.exit_code, "BENCHMARK_DRY_RUN" in result.output) == (0, True)


def test_the_json_output_carries_both_rates(tmp_path: Path) -> None:
    """A consumer needs the two directions separately, as the table reports them."""
    dataset = _dataset(tmp_path, [_record("A finding", "VERIFIED")])
    result = runner.invoke(ai_app, ["prompt-eval", "--json", "--dataset", str(dataset)])
    payload = json.loads(result.stdout)
    assert (result.exit_code, "catch_rate" in payload, "contested_rate" in payload) == (
        0,
        True,
        True,
    )


def test_a_dataset_outside_the_repository_is_refused() -> None:
    """The path is attacker-influenceable through a flag; traversal must not resolve."""
    with pytest.raises(SecurityError):
        evaluate_persona_prompts("devsecops", dataset_path=Path("/etc/passwd"))
