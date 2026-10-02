"""Tests for evaluation history, comparison, and regression checks (#555).

Verifies get_run lookups, setup diffing, metric and backend share comparisons,
baseline setting/getting/listing, and regression checks via library APIs and the CLI.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.run_store import (
    Mechanism,
    RegressionTolerances,
    RunIndex,
    RunRecord,
    check_regression,
    compare_runs,
    diff_setup,
    extract_metrics,
    get_baseline,
    get_run,
    list_baselines,
    new_run,
    save_run,
    set_baseline,
)
from devops_cli.commands import ai_runs
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


class FakeValkey:
    """In-memory Valkey client for testing index operations."""

    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.host, self.port, self.closed = "index.example.com", 6379, False

    def _run(self, name: str, *args: Any) -> Any:
        if name == "SET":
            self.strings[args[0]] = str(args[1])
            return "OK"
        if name == "ZADD":
            self.sorted_sets.setdefault(args[0], {})[args[2]] = float(args[1])
            return 1
        if name == "ZRANGE":
            members = self.sorted_sets.get(args[0], {})
            return sorted(members, key=lambda m: (members[m], m))
        raise AssertionError(f"unexpected command {name}")

    def pipeline(self, commands: list[list[Any]]) -> list[Any]:
        return [self._run(*cmd) for cmd in commands]

    def execute(self, *parts: Any) -> Any:
        return self._run(*parts)

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def set(self, key: str, value: str) -> bool:
        self.strings[key] = value
        return True

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def run_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up an isolated data dir and run environment."""
    data_dir = tmp_path / ".data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))
    return data_dir


@pytest.fixture
def fake_index(monkeypatch: pytest.MonkeyPatch) -> FakeValkey:
    """A reachable fake Valkey index."""
    fake = FakeValkey()
    monkeypatch.setattr(RunIndex, "from_settings", classmethod(lambda cls: cls(fake)))
    return fake


def _sample_run(
    mechanism: Mechanism = Mechanism.REVIEW_BENCHMARK,
    *,
    setup: dict[str, Any] | None = None,
    subject: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
) -> RunRecord:
    default_setup = {
        "models": {"analysis": "gateway/qwen-review"},
        "page_chars": 4000,
        "pool": [{"backend": "vllm-a", "weight": 5}],
    }
    default_subject = {"target": "repo", "corpus_digest": "abcdef1234567890"}
    default_results = {
        "median_wall_seconds": 12.5,
        "total_prompt_tokens": 8500,
        "total_completion_tokens": 1200,
        "recall": 0.85,
        "median_llm_calls": 4,
        "stages": [
            {
                "name": "analysis",
                "backend_busy_share": {"vllm-a": 0.75, "vllm-b": 0.25},
            }
        ],
    }
    return new_run(
        mechanism,
        setup=default_setup if setup is None else setup,
        subject=default_subject if subject is None else subject,
        results=default_results if results is None else results,
    )


def test_get_run_exact_and_prefix(run_env: Path) -> None:
    """Verify get_run finds records by exact ID and prefix."""
    rec = _sample_run()
    save_run(rec)

    found_exact = get_run(rec.run_id)
    found_prefix = get_run(rec.run_id[:12])
    found_mech = get_run(rec.run_id, mechanism=Mechanism.REVIEW_BENCHMARK)
    missing = get_run("nonexistent-run-id")

    assert (
        found_exact is not None and found_exact.run_id == rec.run_id,
        found_prefix is not None and found_prefix.run_id == rec.run_id,
        found_mech is not None and found_mech.run_id == rec.run_id,
        missing,
    ) == (True, True, True, None)


def test_get_run_valkey_fallback(run_env: Path, fake_index: FakeValkey) -> None:
    """Verify get_run retrieves from shared index when absent from local disk."""
    rec = _sample_run()
    with RunIndex(fake_index) as index:  # type: ignore[arg-type]
        index.put(rec)

    found = get_run(rec.run_id)
    found_by_mech = get_run(rec.run_id, mechanism=Mechanism.REVIEW_BENCHMARK)

    assert (
        found is not None and found.run_id == rec.run_id,
        found_by_mech is not None and found_by_mech.run_id == rec.run_id,
    ) == (True, True)


def test_diff_setup_identical_and_differing() -> None:
    """Verify diff_setup returns empty dict for matching configs and details differences."""
    run_a = _sample_run(setup={"model": "m1", "page": 100})
    run_b = _sample_run(setup={"model": "m1", "page": 100})
    run_c = _sample_run(setup={"model": "m2", "page": 100, "extra": True})

    diff_ab = diff_setup(run_a, run_b)
    diff_ac = diff_setup(run_a, run_c)

    assert (
        diff_ab,
        diff_ac["model"],
        diff_ac["extra"],
    ) == (
        {},
        ("m1", "m2"),
        (None, True),
    )


def test_extract_metrics_and_backend_shares() -> None:
    """Verify standard metrics and backend busy shares are cleanly extracted."""
    rec = _sample_run()
    metrics, backend_shares = extract_metrics(rec)

    assert (
        metrics["wall_seconds"],
        metrics["prompt_tokens"],
        metrics["completion_tokens"],
        metrics["recall"],
        metrics["llm_calls"],
        backend_shares,
    ) == (
        12.5,
        8500.0,
        1200.0,
        0.85,
        4.0,
        {"vllm-a": 0.75, "vllm-b": 0.25},
    )


def test_compare_runs_metrics_and_shares() -> None:
    """Verify compare_runs computes accurate absolute and percent deltas."""
    base = _sample_run(
        results={
            "median_wall_seconds": 10.0,
            "total_prompt_tokens": 1000,
            "recall": 0.80,
            "stages": [{"backend_busy_share": {"vllm-a": 0.80}}],
        }
    )
    current = _sample_run(
        results={
            "median_wall_seconds": 12.0,
            "total_prompt_tokens": 1100,
            "recall": 0.84,
            "stages": [{"backend_busy_share": {"vllm-a": 0.60}}],
        }
    )

    comparison = compare_runs(base, current)
    wall_diff = comparison.metrics["wall_seconds"]
    recall_diff = comparison.metrics["recall"]
    backend_diff = comparison.backend_shares["vllm-a"]

    assert (
        comparison.same_fingerprint,
        wall_diff.absolute_change,
        wall_diff.percent_change,
        recall_diff.absolute_change,
        recall_diff.percent_change,
        backend_diff.absolute_change,
    ) == (
        True,
        2.0,
        20.0,
        0.04,
        5.0,
        -0.2,
    )


def test_baseline_management(run_env: Path, fake_index: FakeValkey) -> None:
    """Verify setting, retrieving, and listing baselines across disk and index."""
    rec1 = _sample_run(subject={"dataset": "ds1"})
    rec2 = _sample_run(subject={"dataset": "ds2"})
    save_run(rec1)
    save_run(rec2)

    b1 = set_baseline(rec1)
    b2 = set_baseline(rec2)

    found_b1 = get_baseline(rec1.mechanism, rec1.subject_key)
    baselines = list_baselines()

    assert (
        b1.run_id,
        found_b1 is not None and found_b1.run_id == rec1.run_id,
        [b.run_id for b in baselines],
    ) == (
        rec1.run_id,
        True,
        [b2.run_id, b1.run_id],
    )


def test_check_regression_verdicts() -> None:
    """Verify check_regression flags recall drops and resource increases exceeding tolerances."""
    base = _sample_run(
        results={"median_wall_seconds": 10.0, "total_prompt_tokens": 1000, "recall": 0.90}
    )
    passed_run = _sample_run(
        results={"median_wall_seconds": 11.0, "total_prompt_tokens": 1050, "recall": 0.90}
    )
    failed_run = _sample_run(
        results={"median_wall_seconds": 15.0, "total_prompt_tokens": 1500, "recall": 0.70}
    )

    comp_pass = compare_runs(base, passed_run)
    comp_fail = compare_runs(base, failed_run)

    report_pass = check_regression(
        comp_pass,
        RegressionTolerances(
            max_recall_drop=0.0, max_duration_increase=0.15, max_tokens_increase=0.20
        ),
    )
    report_fail = check_regression(
        comp_fail,
        RegressionTolerances(
            max_recall_drop=0.05, max_duration_increase=0.20, max_tokens_increase=0.20
        ),
    )

    verdicts_fail = {v.metric: v.passed for v in report_fail.verdicts}

    assert (
        report_pass.passed,
        report_fail.passed,
        verdicts_fail,
    ) == (
        True,
        False,
        {"recall": False, "wall_seconds": False, "prompt_tokens": False},
    )


def test_cli_runs_list_and_show(run_env: Path) -> None:
    """Verify devops ai runs list and show outputs."""
    rec = _sample_run()
    save_run(rec)

    res_list = cli.invoke(app, ["ai", "runs", "list"])
    res_list_json = cli.invoke(app, ["ai", "runs", "list", "--format", "json"])
    res_show = cli.invoke(app, ["ai", "runs", "show", rec.run_id])
    res_show_json = cli.invoke(app, ["ai", "runs", "show", rec.run_id, "--format", "json"])
    res_missing = cli.invoke(app, ["ai", "runs", "show", "nonexistent"])

    parsed_list = json.loads(res_list_json.stdout)
    parsed_show = json.loads(res_show_json.stdout)

    assert (
        res_list.exit_code,
        rec.run_id in res_list.stdout,
        res_list_json.exit_code,
        len(parsed_list),
        res_show.exit_code,
        "Run Metadata" in res_show.stdout,
        parsed_show["run_id"],
        res_missing.exit_code,
    ) == (
        0,
        True,
        0,
        1,
        0,
        True,
        rec.run_id,
        1,
    )


def test_cli_runs_baseline_commands(run_env: Path) -> None:
    """Verify devops ai runs baseline set, list, and show."""
    rec = _sample_run()
    save_run(rec)

    res_set = cli.invoke(app, ["ai", "runs", "baseline", "set", rec.run_id])
    res_list = cli.invoke(app, ["ai", "runs", "baseline", "list"])
    res_show = cli.invoke(app, ["ai", "runs", "baseline", "show", rec.run_id])
    res_show_subj = cli.invoke(app, ["ai", "runs", "baseline", "show", rec.subject_key])

    assert (
        res_set.exit_code,
        "Designated run" in res_set.stdout,
        res_list.exit_code,
        rec.run_id in res_list.stdout,
        res_show.exit_code,
        res_show_subj.exit_code,
    ) == (
        0,
        True,
        0,
        True,
        0,
        0,
    )


def test_cli_runs_compare_and_check(run_env: Path) -> None:
    """Verify devops ai runs compare and check CLI subcommands."""
    base = _sample_run(
        results={"median_wall_seconds": 10.0, "total_prompt_tokens": 1000, "recall": 0.90}
    )
    current = _sample_run(
        results={"median_wall_seconds": 11.0, "total_prompt_tokens": 1050, "recall": 0.90}
    )
    regressed = _sample_run(
        results={"median_wall_seconds": 20.0, "total_prompt_tokens": 1050, "recall": 0.50}
    )
    save_run(base)
    save_run(current)
    save_run(regressed)

    set_baseline(base)

    # Compare 2 runs explicitly
    res_comp_two = cli.invoke(app, ["ai", "runs", "compare", base.run_id, current.run_id])
    # Compare 1 run against its baseline
    res_comp_base = cli.invoke(app, ["ai", "runs", "compare", current.run_id])
    # Compare with json
    res_comp_json = cli.invoke(app, ["ai", "runs", "compare", current.run_id, "--format", "json"])

    # Check passing run
    res_check_pass = cli.invoke(app, ["ai", "runs", "check", current.run_id])
    # Check passing run with json
    res_check_json = cli.invoke(app, ["ai", "runs", "check", current.run_id, "--format", "json"])
    # Check failing run
    res_check_fail = cli.invoke(app, ["ai", "runs", "check", regressed.run_id])

    assert (
        res_comp_two.exit_code,
        "Metrics Comparison" in res_comp_two.stdout,
        res_comp_base.exit_code,
        res_comp_json.exit_code,
        json.loads(res_comp_json.stdout)["same_fingerprint"],
        res_check_pass.exit_code,
        "passed all regression checks" in res_check_pass.stdout,
        res_check_json.exit_code,
        json.loads(res_check_json.stdout)["passed"],
        res_check_fail.exit_code,
        "Regression check failed" in res_check_fail.output,
    ) == (
        0,
        True,
        0,
        0,
        True,
        0,
        True,
        0,
        True,
        1,
        True,
    )


def _corpus_arm(run_id: str, **results: Any) -> RunRecord:
    """A corpus score whose means are fixed and whose `spread`, if any, is given.

    Built directly rather than by `new_run`, which runs git three times for the commit.
    """
    return RunRecord(
        mechanism=Mechanism.CORPUS_SCORE,
        run_id=run_id,
        created_at=datetime.now(UTC),
        version="0",
        setup={"prompt_digest": "d1", "runs": 3},
        subject={"corpus_digest": "c"},
        results={"recall_found": 0.5, "recall_reported": 0.2, **results},
    )


def _table_row(output: str, metric: str) -> str:
    return next(line for line in output.splitlines() if f" {metric} " in line)


# The runs group's own app parses `devops ai runs compare` as the full CLI does, without building
# every `devops ai` command on each invocation.


@pytest.mark.parametrize(
    ("current_results", "expected"),
    [
        ({"spread": {"recall_found": [0.5, 1.0]}}, ((0.25, 0.75), (0.5, 1.0), "overlaps")),
        ({"spread": {"recall_found": [0.8, 1.0]}}, ((0.25, 0.75), (0.8, 1.0), "apart")),
        ({"spread": None}, ((0.25, 0.75), None, "—")),
        ({}, ((0.25, 0.75), None, "—")),
    ],
    ids=["overlapping", "apart", "one-run-score", "no-spread"],
)
def test_comparing_arms_reads_their_difference_against_each_ranges(
    run_env: Path, current_results: dict[str, Any], expected: tuple[Any, ...]
) -> None:
    """Verify each run's range comes from its `spread`, and the compare table marks whether the
    ranges overlap; a run without a range, such as a one-run score, reads `—` (#413)."""
    base = _corpus_arm("20261002T000000Z-base00", spread={"recall_found": [0.25, 0.75]})
    current = _corpus_arm("20261002T000001Z-curr00", **current_results)
    save_run(base)
    save_run(current)

    recall = compare_runs(base, current).metrics["recall_found"]
    result = cli.invoke(ai_runs.app, ["compare", base.run_id, current.run_id])
    row = _table_row(result.stdout, "recall_found")

    assert (result.exit_code, (recall.base_range, recall.current_range, row.split()[-1])) == (
        0,
        expected,
    )


def test_comparing_arms_compares_their_finding_counts_beside_their_ranges(run_env: Path) -> None:
    """Verify the compare reads each arm's mean candidate, invalidated and reported findings,
    each beside its range when the arm's `spread` has one (#413)."""
    base = _corpus_arm(
        "20261002T000000Z-base00",
        candidate_findings=12.3,
        invalidated_findings=4.0,
        reported_findings=8.3,
        spread={"candidate_findings": [10, 14], "reported_findings": [7, 9]},
    )
    current = _corpus_arm(
        "20261002T000001Z-curr00",
        candidate_findings=15.7,
        invalidated_findings=2.0,
        reported_findings=13.7,
        spread={"candidate_findings": [13, 17], "reported_findings": [12, 15]},
    )
    save_run(base)
    save_run(current)

    metrics = compare_runs(base, current).metrics
    result = cli.invoke(ai_runs.app, ["compare", base.run_id, current.run_id])
    counts = ("candidate_findings", "invalidated_findings", "reported_findings")

    assert (
        result.exit_code,
        [
            (m.base_value, m.current_value, m.base_range, m.current_range)
            for m in (metrics[name] for name in counts)
        ],
        [_table_row(result.stdout, name).split()[-1] for name in counts],
    ) == (
        0,
        [
            (12.3, 15.7, (10.0, 14.0), (13.0, 17.0)),
            (4.0, 2.0, None, None),
            (8.3, 13.7, (7.0, 9.0), (12.0, 15.0)),
        ],
        ["overlaps", "—", "apart"],
    )


def test_runs_without_a_spread_compare_without_range_columns(run_env: Path) -> None:
    """Verify runs with no spread have no ranges, and the table adds no range columns (#413)."""
    base = _corpus_arm("20261002T000000Z-base00")
    current = _corpus_arm("20261002T000001Z-curr00", spread=None)
    save_run(base)
    save_run(current)

    comparison = compare_runs(base, current)
    result = cli.invoke(ai_runs.app, ["compare", base.run_id, current.run_id])

    assert (
        result.exit_code,
        {(m.base_range, m.current_range) for m in comparison.metrics.values()},
        "Spread" in result.stdout,
    ) == (0, {(None, None)}, False)
