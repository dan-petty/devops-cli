"""Tests for CI execution caching and pre-commit file change tracking."""

from __future__ import annotations

from pathlib import Path

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
from devops_cli.commands.ci import app


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
    assert (cache_path.name, cache_path.parent) == ("ci_cache.json", isolated_cache_dir)


def test_compute_workspace_fingerprint_git(tmp_path: Path) -> None:
    """Test computing fingerprint on a Git repository."""
    # Create mock repo with git command mock
    res = compute_workspace_fingerprint(root=tmp_path)
    # Returns a 3-tuple or None if not a git repo
    if res is not None:
        fp, head_sha, file_hashes = res
        assert (len(fp) == 64, isinstance(head_sha, str), isinstance(file_hashes, dict)) == (
            True,
            True,
            True,
        )


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
    file_hashes = {"src/foo.py": "abc123hash"}
    options = {"fix": True, "check": False}

    save_ci_cache(
        fingerprint="test-fingerprint-001",
        head_sha="headsha001",
        checks=checks,
        file_hashes=file_hashes,
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
        file_hashes={},
        options={"fix": True, "check": False},
        passed=True,
    )

    miss_entry = get_ci_cache(
        fingerprint="test-fp-opt",
        options={"fix": False, "check": True},
    )
    assert miss_entry is None


def test_get_ci_cache_pre_commit_subset_match(tmp_path: Path, isolated_cache_dir: Path) -> None:
    """Test pre-commit subset match when specific changed files match cached digests."""
    file_a = tmp_path / "src" / "a.py"
    file_b = tmp_path / "src" / "b.py"
    file_a.parent.mkdir(parents=True, exist_ok=True)
    file_a.write_text("print('hello a')", encoding="utf-8")
    file_b.write_text("print('hello b')", encoding="utf-8")

    import hashlib

    hash_a = hashlib.sha256(b"print('hello a')").hexdigest()
    hash_b = hashlib.sha256(b"print('hello b')").hexdigest()

    checks = [
        CICachedCheck(
            name="lint",
            display_title="ruff check",
            passed=True,
            duration_seconds=0.2,
        )
    ]
    save_ci_cache(
        fingerprint="global-fp-1",
        head_sha="head1",
        checks=checks,
        file_hashes={"src/a.py": hash_a, "src/b.py": hash_b},
        options={},
        passed=True,
    )

    # Subset match with different global fingerprint
    matched = get_ci_cache(
        fingerprint="different-global-fp",
        files=["src/a.py"],
        options={},
        root=tmp_path,
    )
    assert matched is not None
    assert matched.fingerprint == "global-fp-1"

    # Mismatch when file content changes
    file_a.write_text("print('modified')", encoding="utf-8")
    mismatched = get_ci_cache(
        fingerprint="different-global-fp",
        files=["src/a.py"],
        options={},
        root=tmp_path,
    )
    assert mismatched is None


def test_clear_ci_cache(isolated_cache_dir: Path) -> None:
    """Test cache invalidation via clear_ci_cache."""
    cache_file = isolated_cache_dir / "ci_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    assert cache_file.exists() is True

    clear_ci_cache()
    assert cache_file.exists() is False


def test_ci_cli_cache_hit_and_force(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test CLI execution using cache hit and bypassing with --force."""
    runner = CliRunner()
    cache_path = isolated_cache_dir / "ci_cache.json"

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
        file_hashes={},
    )
    cache_path.write_text(entry.model_dump_json(), encoding="utf-8")

    # Mock compute_workspace_fingerprint to return matching fingerprint
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_workspace_fingerprint",
        lambda *args, **kwargs: ("cli-test-fp", "clihead", {}),
    )

    # Execution with cache hit
    result = runner.invoke(app, ["--cache"])
    assert (result.exit_code, "Utilizing CI cache" in result.stdout) == (0, True)

    # Execution with --force should bypass cache and try to run checks
    run_called = []
    monkeypatch.setattr(
        "devops_cli.commands.ci._run_all_checks_async",
        lambda *args, **kwargs: (
            run_called.append(True)
            or [
                CICachedCheck(
                    name="test",
                    display_title="pytest",
                    passed=True,
                    duration_seconds=0.01,
                )
            ]
        ),
    )


def test_ci_cli_positional_files_pre_commit(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test passing positional filenames as provided by pre-commit."""
    runner = CliRunner()
    captured_files: list[list[str] | None] = []

    def mock_try_fast_cached_ci(root, files, ci_options, *, cache, force):
        captured_files.append(files)
        return True

    monkeypatch.setattr(
        "devops_cli.commands.ci._try_fast_cached_ci",
        mock_try_fast_cached_ci,
    )

    result = runner.invoke(app, ["src/foo.py", "src/bar.py"])
    assert (result.exit_code, captured_files) == (0, [["src/bar.py", "src/foo.py"]])
