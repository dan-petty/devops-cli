"""Unit tests for scanner outcome statuses, applicability preflight, and gating enforcement."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
)
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.security.bandit import BanditScanner
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome, merge_outcomes
from devops_cli.security.pipeline import build_report
from devops_cli.security.popeye import PopeyeScanner
from devops_cli.security.registry import global_scanner_registry
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


class _MockScanner(BaseSecurityScanner):
    """Stand-in security scanner that returns a canned outcome or raises an exception."""

    def __init__(
        self,
        name: str,
        outcome: ScanOutcome | None = None,
        *,
        side_effect: Exception | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.binary_name = name
        self._outcome = outcome if outcome is not None else ScanOutcome("ran", [])
        self._side_effect = side_effect
        self.call_count = 0

    def scan(self, target_path: Any, **kwargs: Any) -> ScanOutcome:
        self.call_count += 1
        if self._side_effect is not None:
            raise self._side_effect
        return self._outcome

    def build_command(self, target_path: Any, **kwargs: Any) -> list[str]:
        return [self.binary_name, str(target_path)]

    def parse_output(self, data: Any, target_path: Any) -> list[Finding]:
        return []


def test_scan_outcome_model_properties_and_equality() -> None:
    """ScanOutcome encapsulates status, findings, and reason while behaving as a list."""
    finding = Finding(
        severity="HIGH",
        location="src/auth.py:42",
        title="Hardcoded token",
        description="Found token in source",
        fix="Use environment variable",
    )
    outcome = ScanOutcome(status="ran", findings=[finding], reason="Completed scan")

    assert (outcome.status, outcome.reason, len(outcome), outcome[0].title) == (
        "ran",
        "Completed scan",
        1,
        "Hardcoded token",
    )
    assert outcome == ScanOutcome(status="ran", findings=[finding], reason="Completed scan")
    assert "ScanOutcome(status='ran'" in repr(outcome)


def test_a_scan_outcome_keeps_the_files_it_did_not_scan_with_their_reasons() -> None:
    """`unscanned` maps each file a scan left out to the reason, and takes part in equality."""
    outcome = ScanOutcome("coverage_gap", unscanned={"style.css": "no rule applies"})

    assert (
        outcome.unscanned,
        outcome == ScanOutcome("coverage_gap", unscanned={"style.css": "no rule applies"}),
        outcome == ScanOutcome("coverage_gap"),
        ScanOutcome("ran").unscanned,
    ) == ({"style.css": "no rule applies"}, True, False, {})


def test_merged_outcomes_keep_the_files_every_run_did_not_scan() -> None:
    """A scanner's batches merge into one outcome that lists the files of each batch that
    left some out, with the worst status of the batches (#1144)."""
    merged = merge_outcomes(
        [
            ScanOutcome("coverage_gap", unscanned={"a.css": "first batch"}),
            ScanOutcome("ran"),
            ScanOutcome("coverage_gap", unscanned={"b.css": "third batch"}),
        ]
    )

    assert (merged.status, merged.unscanned) == (
        "coverage_gap",
        {"a.css": "first batch", "b.css": "third batch"},
    )


def test_merged_outcomes_keep_the_earliest_start_and_latest_end_times() -> None:
    """The merged outcome spans from the earliest run's start to the latest run's end."""
    first = ScanOutcome("ran")
    first.started_utc = "2026-10-01T12:00:01.000Z"
    first.ended_utc = "2026-10-01T12:00:03.000Z"

    second = ScanOutcome("ran")
    second.started_utc = "2026-10-01T12:00:00.000Z"
    second.ended_utc = "2026-10-01T12:00:02.000Z"

    merged = merge_outcomes([first, second])
    assert (merged.started_utc, merged.ended_utc) == (
        "2026-10-01T12:00:00.000Z",
        "2026-10-01T12:00:03.000Z",
    )


def test_popeye_applicability_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Popeye determines applicability before the binary presence check."""
    popeye = PopeyeScanner()

    pop_no_ctx = popeye.is_applicable(tmp_path)
    pop_with_ctx = popeye.is_applicable(tmp_path, context="test-cluster")

    assert (pop_no_ctx[0], pop_with_ctx) == (False, (True, ""))

    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    assert popeye.scan(tmp_path).status == "not_applicable"


@pytest.mark.usefixtures("cached_default_ruleset")
def test_single_scanner_commands_not_run_when_unavailable_or_failed(
    tmp_path: Path,
    cli: Callable[..., Any],
    scanner_fake: ScannerFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-scanner commands display 'not run' and never claim 'passed' when unrun."""
    # Unavailable: binary not found on PATH
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))
    res_unavail = cli(["scan", "sast", str(tmp_path)])
    assert (
        res_unavail.exit_code,
        "Semgrep was not run" in res_unavail.output,
        "No static AST pattern flaws detected" in res_unavail.output,
    ) == (0, True, False)

    # Failed: scanner returns exit code 1
    monkeypatch.setenv(
        "PATH", os.pathsep.join([str(scanner_fake.bin_dir), os.environ.get("PATH", "")])
    )
    scanner_fake.script("trivy", ToolAnswer(exit_code=1, stderr="Exit 1: memory exhausted"))
    res_failed = cli(["scan", "trivy", str(tmp_path)])
    assert (
        res_failed.exit_code,
        "Trivy was not run" in res_failed.output,
        "memory exhausted" in res_failed.output,
    ) == (0, True, True)

    # Ran clean: scanner returns exit code 0 with empty findings
    scanner_fake.script(
        "semgrep", ToolAnswer(stdout=json.dumps({"results": [], "errors": []}), exit_code=0)
    )
    res_clean = cli(["scan", "sast", str(tmp_path)])
    assert (
        res_clean.exit_code,
        "No static AST pattern flaws detected" in res_clean.output,
    ) == (0, True)


def test_scan_report_gating_non_gating_findings(tmp_path: Path) -> None:
    """zizmor workflow findings are non-gating and do not trip --fail-on."""
    zizmor_finding = Finding(
        severity="MEDIUM",
        location=f"{tmp_path}/.github/workflows/ci.yml:10",
        title="[zizmor:template-injection] Code injection via template expansion",
        description="A template expansion in a run step holds untrusted input",
        fix="Pass the value through an environment variable",
    )
    bandit_finding = Finding(
        severity="MEDIUM",
        location="app.py:10",
        title="[B101] assert used",
        description="Assert statement used in production code",
        fix="Replace with conditional",
    )

    zizmor_report = build_report(
        {"zizmor": ScanOutcome("ran", [zizmor_finding])},
        tmp_path,
    )
    assert (
        zizmor_report.findings[0].gating,
        zizmor_report.highest_severity(gating_only=True),
        zizmor_report.highest_severity(gating_only=False),
        zizmor_report.exceeds("LOW"),
        zizmor_report.exceeds("MEDIUM"),
    ) == (
        False,
        None,
        "MEDIUM",
        False,
        False,
    )

    combined_report = build_report(
        {
            "zizmor": ScanOutcome("ran", [zizmor_finding]),
            "bandit": ScanOutcome("ran", [bandit_finding]),
        },
        tmp_path,
    )
    assert (
        combined_report.highest_severity(gating_only=True),
        combined_report.exceeds("MEDIUM"),
    ) == (
        "MEDIUM",
        True,
    )


def test_scan_report_fail_on_evaluation(
    tmp_path: Path,
    cli: Callable[..., Any],
    scanner_fake: ScannerFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--fail-on triggers non-zero exit for failed scanners or missing explicit scanners."""
    scanner_fake.script("semgrep", ToolAnswer(exit_code=1, stderr="Process crashed"))
    res_fail = cli(["scan", "report", str(tmp_path), "--scanner", "semgrep", "--fail-on", "LOW"])
    assert (
        res_fail.exit_code,
        "Scanner(s) failed during execution: semgrep" in res_fail.output,
    ) == (1, True)

    # Explicitly requesting an unavailable scanner with --fail-on must exit 1
    monkeypatch.setenv("PATH", str(tmp_path / "no-binaries"))
    res_explicit = cli(
        ["scan", "report", str(tmp_path), "--scanner", "semgrep", "--fail-on", "LOW"],
    )
    assert (
        res_explicit.exit_code,
        "Requested scanner(s) did not run: semgrep" in res_explicit.output,
    ) == (1, True)

    # Default run with optional missing scanner exits 0 and warns
    res_default = cli(
        ["scan", "report", str(tmp_path), "--fail-on", "LOW"],
    )
    assert (
        res_default.exit_code,
        "Scanner 'semgrep' was not run" in res_default.output,
    ) == (0, True)


def test_scan_report_runs_only_the_scanners_it_is_given(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify `scan report --scanner` runs the scanner it names and no other registered one."""
    named = _MockScanner("test_named")
    other = _MockScanner("test_other")
    global_scanner_registry.register(named)
    global_scanner_registry.register(other)
    try:
        result = cli(["scan", "report", str(tmp_path), "--scanner", "test_named", "--json"])
    finally:
        global_scanner_registry._scanners.pop("test_named", None)
        global_scanner_registry._scanners.pop("test_other", None)

    assert (
        result.exit_code,
        named.call_count,
        other.call_count,
        json.loads(result.stdout)["tools"],
    ) == (0, 1, 0, ["test_named"])


def test_scan_report_skips_named_scanners(
    tmp_path: Path, cli: Callable[..., Any], scanner_fake: ScannerFake
) -> None:
    """Verify `scan report --skip` skips the scanner it names and runs other registered ones."""
    named = _MockScanner("test_named")
    other = _MockScanner("test_other")
    global_scanner_registry.register(named)
    global_scanner_registry.register(other)
    try:
        result = cli(["scan", "report", str(tmp_path), "--skip", "test_named", "--json"])
    finally:
        global_scanner_registry._scanners.pop("test_named", None)
        global_scanner_registry._scanners.pop("test_other", None)

    assert (
        result.exit_code,
        named.call_count,
        other.call_count,
        "test_named" not in json.loads(result.stdout)["tools"],
        "test_other" in json.loads(result.stdout)["tools"],
    ) == (0, 0, 1, True, True)


def test_scan_report_cannot_combine_scanner_and_skip(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify combining --scanner and --skip raises an error with exit code 2."""
    named = _MockScanner("test_named")
    global_scanner_registry.register(named)
    try:
        result = cli(
            ["scan", "report", str(tmp_path), "--scanner", "test_named", "--skip", "test_named"]
        )
    finally:
        global_scanner_registry._scanners.pop("test_named", None)

    assert result.exit_code == 2
    assert "Cannot combine --scanner and --skip options." in result.output


def test_scan_report_unknown_skip_scanner(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Verify unknown scanner in --skip raises an error with exit code 2."""
    result = cli(["scan", "report", str(tmp_path), "--skip", "nonexistent_scanner"])
    assert result.exit_code == 2
    assert "Unknown scanner(s): nonexistent_scanner" in result.output


def test_a_scan_outcome_records_when_the_scanner_started_and_finished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SARIF invocations carry the scanner's execution window in UTC."""
    utc_millis = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))
    outcome = BanditScanner().scan(tmp_path)
    assert (
        outcome.status,
        bool(utc_millis.match(outcome.started_utc or "")),
        bool(utc_millis.match(outcome.ended_utc or "")),
        (outcome.started_utc or "") <= (outcome.ended_utc or ""),
    ) == ("unavailable", True, True, True)


# A scanner error carrying a GitHub token, a password in a URL, and far more text than a reason
# may hold. The secrets come first, so a cap alone would keep them (#915).
_TOKEN = "ghp_" + "Q7rT2xW9yB4nM6kP1sD8fG3hJ5lZ0cV2aE7u"
_PASSWORD = "hunter2-correct-horse"
_URL = f"https://deploy:{_PASSWORD}@git.example.com/app.git"
_LEAKY_ERROR = f"clone of {_URL} with {_TOKEN} failed: " + "x" * 5000


class _LeakyScanner(BaseSecurityScanner):
    """A scanner with no built-in patterns, whose failures carry secrets."""

    name = "leaky"
    binary_name = "leaky-bin"

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        return [self.binary_name, str(target_path)]

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        return []


class _LeakyScannerWithPatterns(_LeakyScanner):
    """The same scanner, falling back to built-in patterns when its command fails."""

    has_builtin_patterns = True


class _LeakyCommandScanner(_LeakyScanner):
    """The same scanner, whose command carries the secrets and far more text than a reason may
    hold."""

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        return [self.binary_name, f"--url={_URL}", f"--token={_TOKEN}", "x" * 5000]


class _CrashingScanner(_LeakyScanner):
    """A scanner that crashes when scan() is called."""

    def scan(self, target_path: Any, **kwargs: Any) -> ScanOutcome:
        raise RuntimeError(_LEAKY_ERROR)


def _report_one_scanner(
    tmp_path: Path, scanner: BaseSecurityScanner, cli: Callable[..., Any]
) -> tuple[ScanOutcome, list[str], str, int]:
    """Run one scanner through the registry and `scan report --sarif`.

    Returns its outcome, the SARIF notification texts, the CLI output with whitespace removed
    (so a wrapped line cannot hide a secret) and the exit code.
    """
    global_scanner_registry.register(scanner)
    sarif_path = tmp_path / "report.sarif"
    try:
        outcome = global_scanner_registry.scan_all(tmp_path, names=[scanner.name])[scanner.name]
        result = cli(
            ["scan", "report", str(tmp_path), "--scanner", scanner.name, "--sarif", str(sarif_path)]
        )
    finally:
        global_scanner_registry._scanners.pop(scanner.name, None)

    notes = [
        note["message"]["text"]
        for run in json.loads(sarif_path.read_text(encoding="utf-8"))["runs"]
        for invocation in run.get("invocations", [])
        for note in invocation.get("toolExecutionNotifications", [])
    ]
    return outcome, notes, "".join(result.output.split()), result.exit_code


def _leaks(outcome: ScanOutcome, notes: list[str], output: str) -> list[tuple[str, str]]:
    """Name each place a secret reached: the outcome, the SARIF notifications or the CLI."""
    places = (("outcome", outcome.reason), ("sarif", " ".join(notes)), ("cli", output))
    return [
        (place, secret)
        for place, text in places
        for secret in (_TOKEN, _PASSWORD)
        if secret in text
    ]


@pytest.mark.parametrize(
    ("raised_by", "error"),
    [
        ("scan", RuntimeError(_LEAKY_ERROR)),
        ("command", RuntimeError(_LEAKY_ERROR)),
    ],
    ids=["the scanner raises", "its command raises"],
)
def test_a_scanner_error_reaches_the_outcome_sarif_and_cli_masked_and_bounded(
    tmp_path: Path,
    raised_by: str,
    error: Exception,
    scanner_fake: ScannerFake,
    cli: Callable[..., Any],
) -> None:
    """Verify neither secret survives, and the reason is cut to the shared cap after masking."""
    scanner: BaseSecurityScanner
    if raised_by == "scan":
        scanner = _CrashingScanner()
    else:
        scanner = _LeakyScanner()
        scanner_fake.fail(scanner.binary_name, error)
    outcome, notes, output, exit_code = _report_one_scanner(tmp_path, scanner, cli)

    assert (
        outcome.status,
        _leaks(outcome, notes, output),
        len(outcome.reason),
        notes,
        "".join(outcome.reason.split()) in output,
        "x" * CONST_MAX_ERROR_DETAIL_LENGTH in output,
        exit_code,
    ) == (
        "failed",
        [],
        CONST_MAX_ERROR_DETAIL_LENGTH,
        [f"leaky: failed: {outcome.reason}"],
        True,
        False,
        0,
    )


def test_a_scanner_timeout_says_how_long_it_had_and_quotes_no_command(
    tmp_path: Path, scanner_fake: ScannerFake, cli: Callable[..., Any]
) -> None:
    """Verify a timeout's reason is the time the command had, in the outcome, SARIF and the CLI
    (#1079): it quoted the command, cut to the cap before the timeout, with its secrets masked."""
    scanner = _LeakyCommandScanner()
    scanner_fake.script(
        scanner.binary_name, ToolAnswer(exit_code=CONST_SANDBOX_TIMEOUT_EXIT_CODE, timed_out=True)
    )
    outcome, notes, output, exit_code = _report_one_scanner(tmp_path, scanner, cli)
    reason = f"timed out after {DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS:g} s"

    assert (outcome.status, _leaks(outcome, notes, output), outcome.reason, notes, exit_code) == (
        "failed",
        [],
        reason,
        [f"leaky: failed: {reason}"],
        0,
    )


def test_a_scanner_error_behind_built_in_patterns_is_masked_and_bounded(
    tmp_path: Path, scanner_fake: ScannerFake, cli: Callable[..., Any]
) -> None:
    """Verify the built-in-patterns reason, which quotes the error, is masked before its cap."""
    scanner = _LeakyScannerWithPatterns()
    scanner_fake.fail(scanner.binary_name, RuntimeError(_LEAKY_ERROR))
    outcome, notes, output, exit_code = _report_one_scanner(tmp_path, scanner, cli)

    assert (
        outcome.status,
        _leaks(outcome, notes, output),
        len(outcome.reason),
        outcome.reason.startswith(
            "Scanner error: clone of https://<masked-user>:<masked-password>@git.example.com/"
            "app.git with <masked-github-token> failed: xxx"
        ),
        notes,
        exit_code,
    ) == (
        "built-in patterns",
        [],
        CONST_MAX_ERROR_DETAIL_LENGTH,
        True,
        [f"leaky: built-in patterns: {outcome.reason}"],
        0,
    )


_MARKUP_REASON = "rule file ends early at [/x] in line 3"


@pytest.mark.parametrize(
    ("command", "status", "printed"),
    [
        ("report", "failed", f"Scanner 'leaky' failed during execution: {_MARKUP_REASON}"),
        ("report", "unavailable", f"Scanner 'leaky' was not run ({_MARKUP_REASON})."),
        ("trivy", "failed", f"Trivy was not run (Scanner exited with code 1: {_MARKUP_REASON})."),
    ],
)
def test_a_reason_holding_markup_prints_literally(
    tmp_path: Path,
    command: str,
    status: str,
    printed: str,
    cli: Callable[..., Any],
    scanner_fake: ScannerFake,
) -> None:
    """Verify a reason with a closing tag prints as written and the command still exits 0."""
    outcome = ScanOutcome(status, [], _MARKUP_REASON)
    if command == "report":
        scanner = _MockScanner("leaky", outcome)
        global_scanner_registry.register(scanner)
        try:
            result = cli(["scan", "report", str(tmp_path), "--scanner", "leaky"])
        finally:
            global_scanner_registry._scanners.pop("leaky", None)
    else:
        scanner_fake.script("trivy", ToolAnswer(exit_code=1, stderr=_MARKUP_REASON))
        result = cli(["scan", "trivy", str(tmp_path)])

    assert (result.exit_code, printed in " ".join(result.output.split())) == (0, True)
