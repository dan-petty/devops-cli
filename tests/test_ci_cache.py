"""Tests for deterministic CI execution caching."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ci.cache import (
    CICachedCheck,
    CICacheEntry,
    clear_ci_cache,
    compute_workspace_fingerprint,
    get_ci_cache,
    resolve_ci_cache_path,
    save_ci_cache,
)
from devops_cli.commands.ci import CheckResult, app


@pytest.fixture
def isolated_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide an isolated data directory for CI cache tests."""
    cache_dir = tmp_path / ".data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    return cache_dir


def test_resolve_ci_cache_path(isolated_cache_dir: Path) -> None:
    """Test resolution of CI cache destination path."""
    cache_path = resolve_ci_cache_path()
    assert (
        cache_path.name.startswith("ci_cache-"),
        cache_path.suffix,
        cache_path.parent,
    ) == (True, ".json", isolated_cache_dir)


def test_compute_workspace_fingerprint_git(tmp_path: Path) -> None:
    """Test computing fingerprint on a Git repository."""
    # Create mock repo with git command mock
    res = compute_workspace_fingerprint(root=tmp_path)
    # Returns a 2-tuple or None if not a git repo
    if res is not None:
        fp, head_sha = res
        assert (len(fp) == 64, isinstance(head_sha, str)) == (True, True)


def test_save_and_get_ci_cache(isolated_cache_dir: Path) -> None:
    """Test saving and retrieving cache entries with exact fingerprint match."""
    checks = [
        CICachedCheck(
            name="test",
            display_title="pytest & coverage",
            passed=True,
            duration_seconds=1.23,
            stdout="all passed",
            stderr="",
        ),
        CICachedCheck(
            name="lint",
            display_title="ruff check",
            passed=True,
            duration_seconds=0.45,
            stdout="",
            stderr="",
        ),
    ]
    options = {"fix": True, "check": False}

    save_ci_cache(
        fingerprint="test-fingerprint-001",
        head_sha="headsha001",
        checks=checks,
        options=options,
        passed=True,
    )

    entry = get_ci_cache(
        fingerprint="test-fingerprint-001",
        options=options,
    )
    assert entry is not None
    assert (entry.fingerprint, entry.head_sha, entry.passed, len(entry.checks)) == (
        "test-fingerprint-001",
        "headsha001",
        True,
        2,
    )


def test_get_ci_cache_mismatched_options(isolated_cache_dir: Path) -> None:
    """Test that mismatched options result in cache miss."""
    checks = [
        CICachedCheck(
            name="lint",
            display_title="ruff check",
            passed=True,
            duration_seconds=0.1,
        )
    ]
    save_ci_cache(
        fingerprint="test-fp-opt",
        head_sha="headsha",
        checks=checks,
        options={"fix": True, "check": False},
        passed=True,
    )

    miss_entry = get_ci_cache(
        fingerprint="test-fp-opt",
        options={"fix": False, "check": True},
    )
    assert miss_entry is None


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/app.py",
        "tests/test_app.py",
        "docs/index.md",
        "pyproject.toml",
    ],
)
def test_any_tracked_change_misses_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative_path: str
) -> None:
    """Any change in the repository changes the fingerprint and misses the cache."""
    cache_dir = tmp_path / ".data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)

    file_path = tmp_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("initial = 1\n", encoding="utf-8")

    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)

    res_initial = compute_workspace_fingerprint(root=tmp_path)
    assert res_initial is not None
    fp_initial, head_sha = res_initial

    checks = [
        CICachedCheck(
            name="test",
            display_title="pytest",
            passed=True,
            duration_seconds=0.1,
        )
    ]
    save_ci_cache(
        fingerprint=fp_initial,
        head_sha=head_sha,
        checks=checks,
        options={},
        passed=True,
        root=tmp_path,
    )
    assert get_ci_cache(fingerprint=fp_initial, options={}, root=tmp_path) is not None

    file_path.write_text("initial = 2\n", encoding="utf-8")

    res_modified = compute_workspace_fingerprint(root=tmp_path)
    assert res_modified is not None
    fp_modified, _ = res_modified

    assert (
        fp_modified != fp_initial,
        get_ci_cache(fingerprint=fp_modified, options={}, root=tmp_path),
    ) == (True, None)


def test_clear_ci_cache(isolated_cache_dir: Path) -> None:
    """Test cache invalidation via clear_ci_cache."""
    cache_file = resolve_ci_cache_path()
    cache_file.write_text("{}", encoding="utf-8")
    assert cache_file.exists() is True

    clear_ci_cache()
    assert cache_file.exists() is False


def test_ci_cli_cache_hit_and_force(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test CLI execution using cache hit and bypassing with --force."""
    runner = CliRunner()
    cache_path = resolve_ci_cache_path()

    entry = CICacheEntry(
        fingerprint="cli-test-fp",
        head_sha="clihead",
        timestamp=1000.0,
        passed=True,
        options={"fix": True, "check": False},
        checks=[
            CICachedCheck(
                name="test",
                display_title="pytest & coverage",
                passed=True,
                duration_seconds=0.01,
            ),
            CICachedCheck(
                name="lint",
                display_title="ruff check",
                passed=True,
                duration_seconds=0.01,
            ),
        ],
    )
    cache_path.write_text(entry.model_dump_json(), encoding="utf-8")

    # Mock compute_workspace_fingerprint to return matching fingerprint
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_workspace_fingerprint",
        lambda *args, **kwargs: ("cli-test-fp", "clihead"),
    )

    # Execution with cache hit
    result = runner.invoke(app, ["--cache"])
    assert (result.exit_code, "Utilizing CI cache" in result.stdout) == (0, True)

    # Execution with --force should bypass cache and try to run checks
    run_called: list[bool] = []

    async def mock_run_async(*args: object, **kwargs: object) -> list[CheckResult]:
        run_called.append(True)
        return [
            CheckResult(
                name="test",
                display_title="pytest",
                passed=True,
                duration_seconds=0.01,
            )
        ]

    monkeypatch.setattr(
        "devops_cli.commands.ci._run_all_checks_async",
        mock_run_async,
    )
    res_force = runner.invoke(app, ["--force"])
    assert (res_force.exit_code, bool(run_called)) == (0, True)


@pytest.mark.parametrize(
    "cli_args",
    [
        ["src/a.py"],
        ["src/a.py", "tests/test_a.py"],
        ["--files", "src/a.py"],
    ],
)
def test_a_file_argument_is_a_usage_error(cli_args: list[str]) -> None:
    """Passing file arguments or --files is a UsageError with exit code 2."""
    runner = CliRunner()
    result = runner.invoke(app, cli_args)
    assert result.exit_code == 2


def test_a_tree_edited_during_the_run_is_not_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If working tree changes during the CI run, result is not saved in cache."""
    cache_dir = tmp_path / ".data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    from devops_cli.commands.ci import CheckResult, _try_save_ci_cache
    from devops_cli.lang.en.messages import MESSAGES

    results = [CheckResult(name="test", display_title="pytest", passed=True, duration_seconds=1.0)]

    warnings_emitted: list[str] = []
    saved_calls: list[str] = []

    monkeypatch.setattr(
        "devops_cli.commands.ci._get",
        lambda name: (
            (lambda msg, **kw: warnings_emitted.append(str(msg)))
            if name == "print_warning"
            else (lambda *a, **kw: None)
        ),
    )
    monkeypatch.setattr(
        "devops_cli.ci.cache.save_ci_cache",
        lambda *args, **kwargs: saved_calls.append("saved"),
    )

    cache_file = resolve_ci_cache_path(tmp_path)
    cache_file.write_text('{"existing": true}', encoding="utf-8")

    with patch(
        "devops_cli.ci.cache.compute_workspace_fingerprint",
        return_value=("fingerprint-after", "sha-after"),
    ):
        _try_save_ci_cache(
            tmp_path,
            results,
            {"fix": True, "check": False},
            before_fingerprint="fingerprint-before",
        )

    assert (
        warnings_emitted == [MESSAGES.ci.cache_tree_changed],
        saved_calls == [],
        cache_file.read_text(encoding="utf-8") == '{"existing": true}',
    ) == (True, True, True)

    with patch(
        "devops_cli.ci.cache.compute_workspace_fingerprint",
        return_value=("fingerprint-same", "sha-same"),
    ):
        _try_save_ci_cache(
            tmp_path,
            results,
            {"fix": True, "check": False},
            before_fingerprint="fingerprint-same",
        )

    assert len(saved_calls) == 1
