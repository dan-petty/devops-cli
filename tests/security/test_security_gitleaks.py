"""Unit tests for Gitleaks sub-millisecond secret pre-filter and fallback scanning."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review_schema import DefectClass
from devops_cli.dry_run.state import set_dry_run
from devops_cli.security.base import MaterializedTargets
from devops_cli.security.gitleaks import (
    GitleaksScanner,
    parse_gitleaks_json,
    run_gitleaks_scan,
)
from devops_cli.security.sarif import to_sarif
from devops_cli.security.tool_executor import ToolRequest
from tests.support.builders import make_finding
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


def test_parse_gitleaks_json() -> None:
    raw_data = [
        {
            "RuleID": "aws-access-key-id",
            "Description": "AWS Access Key ID detected",
            "File": "config/aws.env",
            "StartLine": 12,
            "Match": "AKIAIOSFODNN7EXAMPLE",
        },
        {
            "RuleID": "github-pat",
            "Description": "GitHub Personal Access Token",
            "File": "src/auth.py",
            "Line": 45,
            "Match": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        },
    ]

    findings = parse_gitleaks_json(raw_data)
    assert len(findings) == 2
    assert findings[0].location == "config/aws.env:12"
    assert findings[0].severity in ("HIGH", "CRITICAL")
    assert "[GITLEAKS:aws-access-key-id]" in findings[0].title
    assert findings[1].location == "src/auth.py:45"
    assert findings[1].severity == "CRITICAL"


def test_run_gitleaks_scan_missing_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret_file = tmp_path / "secret.env"
    secret_file.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    outcome = run_gitleaks_scan(secret_file)

    assert (outcome.status, len(outcome.findings)) == ("not installed", 0)


def test_run_gitleaks_scan_dry_run(tmp_path: Path) -> None:
    set_dry_run(True)

    findings = run_gitleaks_scan(tmp_path / "test.py")

    assert (len(findings), "[DRY-RUN]" in findings[0].title) == (1, True)


def _leaks_of_its_source(make_leaks: Callable[[str], list[dict[str, Any]]]) -> Any:
    """A Gitleaks that reports `make_leaks(source)` for the sources of the request,
    and exits 1 when it reports a leak."""

    def answer(request: ToolRequest) -> ToolAnswer:
        if request.targets:
            leaks = [leak for target in request.targets for leak in make_leaks(str(target))]
        else:
            leaks = make_leaks(request.arguments[-1])
        return ToolAnswer(exit_code=1 if leaks else 0, stdout=json.dumps(leaks))

    return answer


def test_scan_secrets_cli(
    tmp_path: Path, scanner_fake: ScannerFake, cli: Callable[..., Any]
) -> None:
    secret_file = tmp_path / "creds.env"
    secret_file.write_text(
        "API_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz123456\n",
        encoding="utf-8",
    )
    fake_json = """[
        {
            "RuleID": "github-pat",
            "Description": "GitHub Personal Access Token",
            "File": "creds.env",
            "StartLine": 1,
            "Match": "ghp_1234567890abcdefghijklmnopqrstuvwxyz123456"
        }
    ]"""
    scanner_fake.script("gitleaks", ToolAnswer(exit_code=1, stdout=fake_json))

    res_scan = cli(["scan", "secrets", str(secret_file)])
    res_json = cli(["scan", "secrets", str(secret_file), "--json"])

    assert (
        (res_scan.exit_code, "Gitleaks Secret Scan" in res_scan.stdout),
        (res_json.exit_code, "GITLEAKS" in res_json.stdout),
    ) == ((0, True), (0, True))


def test_scan_secrets_without_gitleaks_says_it_did_not_run_and_not_that_it_passed(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gitleaks that no directory of PATH holds is not installed, so `devops scan secrets`, which
    the MCP `scan_secrets` tool runs, says that the scan did not run (#1435)."""
    no_scanners = tmp_path / "no-scanners"
    no_scanners.mkdir()
    monkeypatch.setenv("PATH", str(no_scanners))

    result = cli("scan", "secrets", str(tmp_path))

    assert (result.exit_code, result.output) == (
        0,
        f"Executing Gitleaks secret scan on '{tmp_path.resolve()}'...\n"
        "! Gitleaks was not run (Binary 'gitleaks' not found on PATH).\n",
    )


_GITHUB_PAT = (
    "Uncovered a GitHub Personal Access Token, potentially leading to unauthorized repository "
    "access and sensitive content exposure."
)


def _leaked_settings(tmp_path: Path) -> Path:
    """The file of Gitleaks' recorded run that finds a leak. The recording ran over a GitHub token;
    the report is redacted, so this file holds none."""
    tree = tmp_path / "tree"
    tree.mkdir()
    settings = tree / "settings.py"
    settings.write_text("token = None\n", encoding="utf-8")
    return settings


def test_a_leak_that_gitleaks_reports_is_a_finding_of_a_scan_that_ran(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """Gitleaks writes its report on stdout only with `--report-path -`, and exits 1 when it finds
    a leak. The scan ran, and the leak is its finding (#1434)."""
    settings = _leaked_settings(tmp_path)
    recorded = scanner_fake.script_run_with_findings("gitleaks", tree=settings.parent)

    outcome = run_gitleaks_scan(settings)

    assert (scanner_fake.runs, outcome.status, outcome.findings) == (
        [recorded],
        "ran",
        [
            make_finding(
                severity="CRITICAL",
                location=f"{settings}:1",
                title=f"[GITLEAKS:github-pat] {_GITHUB_PAT}",
                description=f"Gitleaks detected secret rule pattern 'github-pat' at {settings}:1: "
                f"{_GITHUB_PAT}",
                fix="Remove plaintext credentials from source control and store securely in OS "
                "Keyring.",
                confidence_score=None,
                category=DefectClass.SECRET_EXPOSURE.value,
            )
        ],
    )


def test_the_agent_gitleaks_tool_reports_the_leak_that_gitleaks_found(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The agent tool `scan_gitleaks` reports the leak that Gitleaks found, and not that the scan
    gave no result (#1434)."""
    from devops_cli.ai.tools.builtin_tools import scan_gitleaks

    settings = _leaked_settings(tmp_path)
    recorded = scanner_fake.script_run_with_findings("gitleaks", tree=settings.parent)
    monkeypatch.chdir(tmp_path)

    reply = scan_gitleaks(str(settings))

    assert (scanner_fake.runs, reply) == (
        [recorded],
        "Gitleaks scan status: ok\n"
        "Findings (1):\n"
        f"- [CRITICAL] {settings}:1: [GITLEAKS:github-pat] {_GITHUB_PAT} (Remove plaintext "
        "credentials from source control and store securely in OS Keyring.)",
    )


def test_gitleaks_binary_mocked_execution(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """Verify mocked binary JSON output parsing and location extraction."""
    patterns_file = tmp_path / "all_secrets.txt"
    patterns_file.write_text("KEY=fake\n", encoding="utf-8")

    fake_gitleaks_json = """[
        {
            "RuleID": "generic-api-key",
            "Description": "Generic API Key",
            "File": "config/keys.env",
            "StartLine": 5,
            "Match": "secret12345"
        }
    ]"""
    scanner_fake.script("gitleaks", ToolAnswer(stdout=fake_gitleaks_json))

    res_scan = run_gitleaks_scan([patterns_file])

    assert (len(res_scan), res_scan[0].location) == (1, "config/keys.env:5")


def test_run_gitleaks_scan_ignore_tests(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """Verify ignore_tests=True filters out test fixtures and test file paths."""
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_auth.py"
    test_file.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    src_file = tmp_path / "src_auth.py"
    src_file.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    scanner_fake.answer_with(
        "gitleaks",
        _leaks_of_its_source(
            lambda source: [
                {
                    "RuleID": "aws-key",
                    "Description": "AWS Key",
                    "File": source,
                    "StartLine": 1,
                    "Match": "AKIAIOSFODNN7EXAMPLE",
                }
            ]
        ),
    )

    # Scanning test file directly with ignore_tests=True returns no findings
    res_test_ignored = run_gitleaks_scan(test_file, ignore_tests=True)
    assert len(res_test_ignored) == 0

    # Scanning test file with ignore_tests=False returns findings
    res_test_included = run_gitleaks_scan(test_file, ignore_tests=False)
    assert len(res_test_included) >= 1

    # Scanning list containing both ignores the test file
    res_dir = run_gitleaks_scan([test_file, src_file], ignore_tests=True)
    assert (len(res_dir), "src_auth.py" in res_dir[0].location) == (1, True)


def test_run_gitleaks_scan_ignore_tests_windows_paths(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify ignore_tests=True properly filters Windows paths (e.g. C:\\...:line)."""
    fake_gitleaks_json = """[
        {
            "RuleID": "generic-api-key",
            "Description": "Generic Key in Test",
            "File": "C:\\\\Users\\\\dev\\\\project\\\\tests\\\\test_login.py",
            "StartLine": 25,
            "Match": "secret12345"
        },
        {
            "RuleID": "generic-api-key",
            "Description": "Generic Key in Source",
            "File": "C:\\\\Users\\\\dev\\\\project\\\\src\\\\login.py",
            "StartLine": 10,
            "Match": "secret12345"
        }
    ]"""
    scanner_fake.script("gitleaks", ToolAnswer(stdout=fake_gitleaks_json))

    # With ignore_tests=True, only the src file is kept
    res_ignored = run_gitleaks_scan(tmp_path, ignore_tests=True)
    assert len(res_ignored) == 1
    assert "login.py" in res_ignored[0].location
    assert "test_login" not in res_ignored[0].location

    # With ignore_tests=False, both are kept
    res_all = run_gitleaks_scan(tmp_path, ignore_tests=False)
    assert len(res_all) == 2


def test_run_gitleaks_scan_list_target_without_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing binary reports not installed with empty findings."""
    clean = tmp_path / "clean.py"
    clean.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    secret = tmp_path / "secret.env"
    secret.write_text("AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    outcome = run_gitleaks_scan([clean, secret])

    assert (outcome.status, len(outcome.findings)) == ("not installed", 0)


def test_run_gitleaks_scan_list_target_runs_binary_once(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """A list target runs Gitleaks once over the directory of materialized targets."""
    first = tmp_path / "first.py"
    first.write_text("x = 1\n", encoding="utf-8")
    second = tmp_path / "second.env"
    second.write_text("TOKEN=redacted\n", encoding="utf-8")
    fake_json = json.dumps(
        [
            {
                "RuleID": "generic-api-key",
                "Description": "Generic API Key",
                "File": "second.env",
                "StartLine": 1,
                "Match": "TOKEN",
            }
        ]
    )
    scanner_fake.script("gitleaks", ToolAnswer(exit_code=1, stdout=fake_json))

    outcome = run_gitleaks_scan([first, second])

    assert len(scanner_fake.runs) == 1
    assert outcome.status == "ran"
    assert [f.location for f in outcome.findings] == ["second.env:1"]


def test_review_starts_gitleaks_once_for_n_files(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """A review of N files starts Gitleaks exactly once on the executor fake, and findings name reviewed files."""
    tree = tmp_path / "tree"
    tree.mkdir()
    first = tree / "first.py"
    first.write_text("x = 1\n", encoding="utf-8")
    second = tree / "second.py"
    second.write_text("TOKEN=secret\n", encoding="utf-8")
    third = tree / "third.py"
    third.write_text("z = 3\n", encoding="utf-8")

    fake_json = json.dumps(
        [
            {
                "RuleID": "generic-api-key",
                "Description": "Generic API Key",
                "File": "second.py",
                "StartLine": 1,
                "Match": "TOKEN",
            }
        ]
    )
    scanner_fake.script("gitleaks", ToolAnswer(exit_code=1, stdout=fake_json))

    outcome = run_gitleaks_scan(
        [first, second, third],
        ignore_tests=True,
        isolated=True,
        tree=tree,
        tool_executor=scanner_fake,
    )

    gitleaks_requests = [r for r in scanner_fake.requests if r.tool == "gitleaks"]
    assert len(gitleaks_requests) == 1
    assert outcome.status == "ran"
    assert len(outcome.findings) == 1
    assert outcome.findings[0].location == "second.py:1"
    assert "devops-scan-gitleaks" not in outcome.findings[0].location
    assert "devops-scan-gitleaks" not in outcome.findings[0].description


def test_gitleaks_scratch_directory_path_is_mapped_to_reviewed_file(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Findings that Gitleaks reports with scratch directory paths map back to reviewed files."""
    tree = tmp_path / "tree"
    tree.mkdir()
    secret_file = tree / "config.env"
    secret_file.write_text("SECRET=xyz\n", encoding="utf-8")

    def answer_with_scratch_path(request: ToolRequest) -> ToolAnswer:
        workdir = request.cwd or request.workdir
        fake_json = json.dumps(
            [
                {
                    "RuleID": "generic-api-key",
                    "Description": "Generic API Key",
                    "File": str(workdir / "config.env"),
                    "StartLine": 1,
                    "Match": "SECRET",
                }
            ]
        )
        return ToolAnswer(exit_code=1, stdout=fake_json)

    scanner_fake.answer_with("gitleaks", answer_with_scratch_path)

    outcome = run_gitleaks_scan(
        [secret_file],
        ignore_tests=True,
        isolated=True,
        tree=tree,
        tool_executor=scanner_fake,
    )

    assert outcome.status == "ran"
    assert len(outcome.findings) == 1
    assert outcome.findings[0].location == "config.env:1"
    assert "devops-scan" not in outcome.findings[0].location
    assert "devops-scan" not in outcome.findings[0].description


def test_run_gitleaks_scan_list_target_keeps_start_and_end_times_in_sarif(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """A two-file list scan records execution window and propagates times to SARIF invocation."""
    first = tmp_path / "first.py"
    first.write_text("x = 1\n", encoding="utf-8")
    second = tmp_path / "second.py"
    second.write_text("y = 2\n", encoding="utf-8")

    scanner_fake.script("gitleaks", ToolAnswer(stdout="[]"))

    outcome = run_gitleaks_scan([first, second])

    assert outcome.status == "ran"
    assert outcome.started_utc is not None
    assert outcome.ended_utc is not None
    assert outcome.started_utc <= outcome.ended_utc

    document = to_sarif([], {"gitleaks": outcome})
    run = next(r for r in document["runs"] if r["tool"]["driver"]["name"] == "gitleaks")
    invocation = run["invocations"][0]
    assert invocation["executionSuccessful"] is True
    assert "startTimeUtc" in invocation
    assert "endTimeUtc" in invocation
    assert invocation["startTimeUtc"] == outcome.started_utc
    assert invocation["endTimeUtc"] == outcome.ended_utc
    assert invocation["startTimeUtc"] <= invocation["endTimeUtc"]


def test_parse_output_ignores_isolation_files(tmp_path: Path) -> None:
    """Findings for internal isolation files like gitleaks.toml and .gitleaksignore stay ignored."""
    scanner = GitleaksScanner()
    staged = MaterializedTargets({"app.py": tmp_path / "app.py"})
    raw_data = [
        {"RuleID": "secret", "File": "gitleaks.toml", "Line": 1},
        {"RuleID": "secret", "File": "/workdir/.gitleaksignore", "Line": 1},
        {"RuleID": "secret", "File": "app.py", "Line": 2},
        None,
    ]
    findings = scanner.parse_output(raw_data, staged)
    assert len(findings) == 1
    assert findings[0].location == "app.py:2"


def test_build_command_and_dry_run_with_materialized_and_list_targets(tmp_path: Path) -> None:
    """`build_command` and `dry_run_scan` support MaterializedTargets and list targets."""
    scanner = GitleaksScanner()
    target_file = tmp_path / "app.py"
    target_file.write_text("x = 1\n", encoding="utf-8")
    staged = MaterializedTargets({"app.py": target_file})

    cmd_list = scanner.build_command([target_file])
    assert cmd_list[-1] == str(target_file)

    dry_run = scanner.dry_run_scan(staged)
    assert len(dry_run) == 1
    assert str(target_file) in dry_run[0].location


def test_isolated_targets_empty_list_and_no_repo_root(tmp_path: Path) -> None:
    """`isolated_targets` handles empty target lists and files outside a git repository."""
    scanner = GitleaksScanner()
    workdir = tmp_path / "workdir"
    workdir.mkdir()

    empty = scanner.isolated_targets([], workdir)
    assert isinstance(empty, MaterializedTargets)
    assert len(empty.origins) == 0

    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    staged = scanner.isolated_targets([outside], workdir)
    assert isinstance(staged, MaterializedTargets)
    assert "outside.py" in staged.origins
