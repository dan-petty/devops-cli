"""Tests verifying dry-run classifications, request plans, and invariants for devops review commands (#2248).

All 20 review commands (and their 20 ai review aliases) are classified under the owner's dry-run
rule (#412):
- 12 commands with external requests carry 'request-plan' and render planned requests in dry run.
- 1 mutating local command ('review export-feedback') carries 'no-external-request' and previews
  without writing state.
- 7 read-only/local inspection commands carry 'no-external-request' and run normally under dry run.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.review import (
    app as review_app,
)
from devops_cli.commands.review import (
    benchmark as cmd_benchmark,
)
from devops_cli.commands.review import (
    branch as cmd_branch,
)
from devops_cli.commands.review import (
    corpus_generate as cmd_corpus_generate,
)
from devops_cli.commands.review import (
    corpus_score as cmd_corpus_score,
)
from devops_cli.commands.review import (
    export_feedback as cmd_export_feedback,
)
from devops_cli.commands.review import (
    intake as cmd_intake,
)
from devops_cli.commands.review import (
    list_findings as cmd_list_findings,
)
from devops_cli.commands.review import (
    path as cmd_path,
)
from devops_cli.commands.review import (
    pr as cmd_pr,
)
from devops_cli.commands.review import (
    review_main,
)
from devops_cli.commands.review import (
    review_score as cmd_review_score,
)
from devops_cli.commands.review import (
    review_stats as cmd_review_stats,
)
from devops_cli.commands.review import (
    rules_test as cmd_rules_test,
)
from devops_cli.commands.review import (
    samples_fetch as cmd_samples_fetch,
)
from devops_cli.commands.review import (
    samples_list as cmd_samples_list,
)
from devops_cli.commands.review import (
    samples_validate as cmd_samples_validate,
)
from devops_cli.commands.review import (
    templates_check as cmd_templates_check,
)
from devops_cli.commands.review import (
    templates_list as cmd_templates_list,
)
from devops_cli.commands.review import (
    verify_finding as cmd_verify_finding,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

REQUEST_PLAN_COMMANDS: list[tuple[str, Any, list[str]]] = [
    ("review benchmark", cmd_benchmark, ["review", "benchmark", "src/", "--dry-run"]),
    ("review branch", cmd_branch, ["review", "branch", "main", "--dry-run"]),
    (
        "review corpus generate",
        cmd_corpus_generate,
        ["review", "corpus", "generate", "src/", "--dry-run"],
    ),
    (
        "review corpus score",
        cmd_corpus_score,
        ["review", "corpus", "score", "tests/fixtures", "--dry-run"],
    ),
    ("review path", cmd_path, ["review", "path", "src/", "--dry-run"]),
    ("review pr", cmd_pr, ["review", "pr", "42", "--repo", "dan-petty/devops-cli", "--dry-run"]),
    ("review samples fetch", cmd_samples_fetch, ["review", "samples", "fetch", "--dry-run"]),
    (
        "review samples validate",
        cmd_samples_validate,
        ["review", "samples", "validate", "--dry-run"],
    ),
    (
        "review score",
        cmd_review_score,
        ["review", "score", "--labels", "labels.json", "s1", "--dry-run"],
    ),
    ("review templates check", cmd_templates_check, ["review", "templates", "check", "--dry-run"]),
    ("review templates sweep", cmd_templates_check, ["review", "templates", "sweep", "--dry-run"]),
    ("ai review benchmark", cmd_benchmark, ["ai", "review", "benchmark", "src/", "--dry-run"]),
    ("ai review branch", cmd_branch, ["ai", "review", "branch", "main", "--dry-run"]),
    (
        "ai review corpus generate",
        cmd_corpus_generate,
        ["ai", "review", "corpus", "generate", "src/", "--dry-run"],
    ),
    (
        "ai review corpus score",
        cmd_corpus_score,
        ["ai", "review", "corpus", "score", "tests/fixtures", "--dry-run"],
    ),
    ("ai review path", cmd_path, ["ai", "review", "path", "src/", "--dry-run"]),
    (
        "ai review pr",
        cmd_pr,
        ["ai", "review", "pr", "42", "--repo", "dan-petty/devops-cli", "--dry-run"],
    ),
    (
        "ai review samples fetch",
        cmd_samples_fetch,
        ["ai", "review", "samples", "fetch", "--dry-run"],
    ),
    (
        "ai review samples validate",
        cmd_samples_validate,
        ["ai", "review", "samples", "validate", "--dry-run"],
    ),
    (
        "ai review score",
        cmd_review_score,
        ["ai", "review", "score", "--labels", "labels.json", "s1", "--dry-run"],
    ),
    (
        "ai review templates check",
        cmd_templates_check,
        ["ai", "review", "templates", "check", "--dry-run"],
    ),
    (
        "ai review templates sweep",
        cmd_templates_check,
        ["ai", "review", "templates", "sweep", "--dry-run"],
    ),
]

NO_EXTERNAL_REQUEST_COMMANDS: list[tuple[str, Any, list[str]]] = [
    ("review (callback)", review_main, ["--dry-run", "review", "--explain"]),
    ("review findings", cmd_list_findings, ["--dry-run", "review", "findings"]),
    ("review rules test", cmd_rules_test, ["--dry-run", "review", "rules", "test"]),
    ("review samples list", cmd_samples_list, ["--dry-run", "review", "samples", "list"]),
    ("review stats", cmd_review_stats, ["--dry-run", "review", "stats"]),
    ("review templates list", cmd_templates_list, ["--dry-run", "review", "templates", "list"]),
    ("ai review (callback)", review_main, ["--dry-run", "ai", "review", "--explain"]),
    ("ai review findings", cmd_list_findings, ["--dry-run", "ai", "review", "findings"]),
    ("ai review rules test", cmd_rules_test, ["--dry-run", "ai", "review", "rules", "test"]),
    ("ai review samples list", cmd_samples_list, ["--dry-run", "ai", "review", "samples", "list"]),
    ("ai review stats", cmd_review_stats, ["--dry-run", "ai", "review", "stats"]),
    (
        "ai review templates list",
        cmd_templates_list,
        ["--dry-run", "ai", "review", "templates", "list"],
    ),
]

ALL_20_CALLBACKS: list[tuple[str, Any, str]] = [
    ("benchmark", cmd_benchmark, "request-plan"),
    ("branch", cmd_branch, "request-plan"),
    ("corpus generate", cmd_corpus_generate, "request-plan"),
    ("corpus score", cmd_corpus_score, "request-plan"),
    ("intake", cmd_intake, "request-plan"),
    ("path", cmd_path, "request-plan"),
    ("pr", cmd_pr, "request-plan"),
    ("samples fetch", cmd_samples_fetch, "request-plan"),
    ("samples validate", cmd_samples_validate, "request-plan"),
    ("score", cmd_review_score, "request-plan"),
    ("templates check/sweep", cmd_templates_check, "request-plan"),
    ("export-feedback", cmd_export_feedback, "no-external-request"),
    ("review_main", review_main, "no-external-request"),
    ("findings", cmd_list_findings, "no-external-request"),
    ("rules test", cmd_rules_test, "no-external-request"),
    ("samples list", cmd_samples_list, "no-external-request"),
    ("stats", cmd_review_stats, "no-external-request"),
    ("templates list", cmd_templates_list, "no-external-request"),
    ("verify", cmd_verify_finding, "no-external-request"),
]


@pytest.fixture(autouse=True)
def guard_no_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure dry-run previews make zero network, subprocess or database calls."""
    real_run = subprocess.run
    real_popen = subprocess.Popen
    real_check_output = subprocess.check_output

    def _block_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Network socket call attempted during dry-run preview")

    def _block_subprocess(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_run(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_popen(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_popen(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_check_output(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_check_output(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_httpx(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HTTP request attempted during dry-run preview")

    monkeypatch.setattr(socket.socket, "connect", _block_socket)
    monkeypatch.setattr(subprocess, "Popen", _block_popen)
    monkeypatch.setattr(subprocess, "run", _block_subprocess)
    monkeypatch.setattr(subprocess, "check_output", _block_check_output)
    monkeypatch.setattr(httpx2.Client, "send", _block_httpx)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", _block_httpx)


def test_dry_run_classes_decorated() -> None:
    """Verify that all review callbacks are decorated with their assigned dry-run class."""
    for name, callback, expected_cls in ALL_20_CALLBACKS:
        actual_cls = get_dry_run_class(callback)
        assert actual_cls == expected_cls, (
            f"Expected {name} to have dry-run class '{expected_cls}', got '{actual_cls}'"
        )


def test_all_40_review_commands_removed_from_gaps() -> None:
    """Verify all 20 review commands and 20 ai review aliases are absent from dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    review_gaps = [cmd for cmd in gaps if cmd.startswith("review") or cmd.startswith("ai review")]
    assert review_gaps == [], f"Found review commands still in gaps: {review_gaps}"


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each request-plan command with --dry-run and verify clean exit and plan output."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in {name} output, got: {result.output}"
    )


def test_review_json_dry_run_formats() -> None:
    """Verify json output formats for review dry runs."""
    res_score = runner.invoke(
        app, ["review", "score", "--labels", "labels.json", "s1", "--dry-run", "--format", "json"]
    )
    assert res_score.exit_code == 0
    data_score = json.loads(res_score.output)
    assert data_score["dry_run"] is True
    assert len(data_score["requests"]) == 1

    res_corpus = runner.invoke(
        app, ["review", "corpus", "score", "tests/fixtures", "--dry-run", "--format", "json"]
    )
    assert res_corpus.exit_code == 0
    data_corpus = json.loads(res_corpus.output)
    assert data_corpus["dry_run"] is True
    assert len(data_corpus["requests"]) == 2

    res_tmpl = runner.invoke(app, ["review", "templates", "check", "--dry-run", "--format", "json"])
    assert res_tmpl.exit_code == 0
    data_tmpl = json.loads(res_tmpl.output)
    assert data_tmpl["dry_run"] is True
    assert len(data_tmpl["requests"]) == 1


def test_review_export_feedback_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify review export-feedback --dry-run previews without writing to disk."""
    out_file = tmp_path / "target_feedback.jsonl"

    def _block_open(path: Any, *args: Any, **kwargs: Any) -> Any:
        if "w" in str(args) or "a" in str(args) or kwargs.get("mode") in ("w", "a"):
            raise AssertionError(f"File write attempted during dry run: {path}")
        return Path(path).open(*args, **kwargs)

    result = runner.invoke(
        app, ["review", "export-feedback", "--output", str(out_file), "--dry-run"]
    )
    assert result.exit_code == 0, f"export-feedback failed: {result.output}"
    assert not out_file.exists(), "Dry run must not create or write to the output file"
    assert "dry run" in result.output.lower() or "unchanged" in result.output.lower()


@pytest.mark.parametrize("name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test commands classified as no-external-request run normally under --dry-run without error."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"


def test_rules_test_has_no_dry_run_option() -> None:
    """Verify that review rules test no longer exposes --dry-run."""
    result = runner.invoke(review_app, ["rules", "test", "--dry-run"])
    assert result.exit_code != 0
    assert "No such option: --dry-run" in result.output
