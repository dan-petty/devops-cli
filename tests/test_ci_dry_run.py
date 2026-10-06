import platform
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import app, get_check_specs
from devops_cli.dry_run import is_dry_run, set_dry_run

# Pre-warm standard library system cache so uname is not invoked by platform internals
platform.processor()

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_dry_run_state() -> None:
    """Ensure dry-run state is clean before and after each test."""
    set_dry_run(False)
    yield
    set_dry_run(False)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Capture subprocess.run invocations without launching real processes."""
    calls: list[list[str]] = []

    def mock_run(
        cmd: list[str] | tuple[str, ...], *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)
    return calls


def test_ci_lint_dry_run(recorder: list[list[str]]) -> None:
    """devops ci lint --dry-run prints a one-request plan and starts zero processes."""
    res = runner.invoke(app, ["lint", "--dry-run"])
    expected_cmd = "uv --preview-features malware-check,check-command run ruff check --fix ."
    assert (res.exit_code, len(recorder), is_dry_run()) == (0, 0, True)
    assert f"1. {expected_cmd}" in res.stdout


def test_ci_format_dry_run(recorder: list[list[str]]) -> None:
    """devops ci format --dry-run prints a one-request plan and starts zero processes."""
    res = runner.invoke(app, ["format", "--dry-run"])
    expected_cmd = "uv --preview-features malware-check,check-command run ruff format ."
    assert (res.exit_code, len(recorder), is_dry_run()) == (0, 0, True)
    assert f"1. {expected_cmd}" in res.stdout


def test_ci_test_dry_run(recorder: list[list[str]]) -> None:
    """devops ci test --dry-run prints a one-request plan and starts zero processes."""
    res = runner.invoke(app, ["test", "-n", "2", "-k", "unit", "--dry-run"])
    assert (res.exit_code, len(recorder), is_dry_run()) == (0, 0, True)
    assert "pytest -n 2 -k unit" in res.stdout


def test_ci_coverage_dry_run(recorder: list[list[str]]) -> None:
    """devops ci coverage --dry-run prints a one-request plan and starts zero processes."""
    res = runner.invoke(app, ["coverage", "--dry-run"])
    assert (res.exit_code, len(recorder), is_dry_run()) == (0, 0, True)
    assert "--cov=src" in res.stdout


def test_ci_coverage_build_index_dry_run(
    recorder: list[list[str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """devops ci coverage --build-index --dry-run plans the index run and writes no index."""
    index_file = tmp_path / "coverage_index.json"
    monkeypatch.setattr("devops_cli.ci.cache.resolve_coverage_index_path", lambda _root: index_file)
    res = runner.invoke(app, ["coverage", "--build-index", "--dry-run"])
    assert (res.exit_code, len(recorder), index_file.exists(), is_dry_run()) == (
        0,
        0,
        False,
        True,
    )
    assert ("COVERAGE_CORE=ctrace", "--cov-context=test") == (
        "COVERAGE_CORE=ctrace" if "COVERAGE_CORE=ctrace" in res.stdout else "",
        "--cov-context=test" if "--cov-context=test" in res.stdout else "",
    )


def test_ci_all_checks_dry_run(recorder: list[list[str]]) -> None:
    """devops ci --dry-run prints fix steps then every row of get_check_specs() without badges."""
    res = runner.invoke(app, ["--dry-run"])
    assert (res.exit_code, len(recorder), is_dry_run()) == (0, 0, True)
    specs = get_check_specs()
    # 3 fix steps (format, lint, docs) + 12 check spec rows
    assert (
        "1. uv --preview-features malware-check,check-command run ruff format ." in res.stdout,
        "2. uv --preview-features malware-check,check-command run ruff check --fix ." in res.stdout,
        "3. uv --preview-features malware-check,check-command run devops docs generate --sync-readme"
        in res.stdout,
    ) == (True, True, True)
    for spec in specs:
        target_name = spec.cmd[2] if len(spec.cmd) > 2 and spec.cmd[0] == "uv" else spec.cmd[1]
        assert target_name in res.stdout
    # No pass badges or summary table under dry run
    assert ("✓ pass" in res.stdout, "CI Summary" in res.stdout) == (False, False)


def test_ci_run_command_dry_run(recorder: list[list[str]]) -> None:
    """devops ci run --dry-run prints fix steps and checks and exits 0."""
    res = runner.invoke(app, ["run", "--dry-run"])
    assert (res.exit_code, len(recorder), is_dry_run()) == (0, 0, True)
    assert (
        "1. uv --preview-features malware-check,check-command run ruff format ." in res.stdout,
        "2. uv --preview-features malware-check,check-command run ruff check --fix ." in res.stdout,
        "3. uv --preview-features malware-check,check-command run devops docs generate --sync-readme"
        in res.stdout,
    ) == (True, True, True)
    assert ("✓ pass" in res.stdout, "CI Summary" in res.stdout) == (False, False)


def test_ci_dry_run_unlinks_nothing(
    recorder: list[list[str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """devops ci --dry-run and devops ci run --dry-run unlink no coverage files."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: tmp_path)
    cov_worker = tmp_path / ".coverage.sample"
    cov_xml = tmp_path / "coverage.xml"
    cov_worker.write_text("worker data")
    cov_xml.write_text("<xml/>")

    res_ci = runner.invoke(app, ["--dry-run"])
    res_run = runner.invoke(app, ["run", "--dry-run"])

    assert (
        res_ci.exit_code,
        res_run.exit_code,
        cov_worker.exists(),
        cov_xml.exists(),
        len(recorder),
    ) == (0, 0, True, True, 0)


def test_ci_live_control(recorder: list[list[str]], tmp_path: Path) -> None:
    """Without --dry-run, devops ci lint and devops ci --no-cache execute subprocesses."""
    res_lint = runner.invoke(app, ["lint"])
    assert (res_lint.exit_code, len(recorder)) == (0, 1)
    assert recorder[0] == [
        "uv",
        "--preview-features",
        "malware-check,check-command",
        "run",
        "ruff",
        "check",
        "--fix",
        ".",
    ]

    recorder.clear()
    res_ci = runner.invoke(app, ["--no-cache"])
    assert (res_ci.exit_code, len(recorder) > 0) == (0, True)


def test_other_ci_subcommands_dry_run(recorder: list[list[str]]) -> None:
    """Verify other subcommands with --dry-run start zero processes and exit 0."""
    subcmds = [
        ["typecheck", "--dry-run"],
        ["audit", "--dry-run"],
        ["security", "--severity", "high", "--dry-run"],
        ["actionlint", "--dry-run"],
        ["docs", "--dry-run"],
        ["uv-check", "--dry-run"],
        ["lockfile", "--dry-run"],
        ["outdated", "--dry-run"],
    ]
    for subcmd in subcmds:
        res = runner.invoke(app, subcmd)
        assert (subcmd[0], res.exit_code, len(recorder)) == (subcmd[0], 0, 0)
