"""The workspace isolation tripwire: a run that leaves the project's `config.yaml`, a tracked file,
a test-only path or a worker's home changed fails (#749, #1311).

The xdist controller snapshots the project when the session starts and compares it when the
session finishes, so parallel workers do not race. The project is pytest's root directory, read
from the session's config rather than from `tests.support.paths`: a hook module that imported
the paths would make every change to them reach every test (#1312).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.support.bootstrap import is_xdist_worker


def get_git_tracked_files(repo_root: Path) -> list[str]:
    """Return relative paths of all git-tracked files in the repository."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def snapshot_tracked_files(repo_root: Path, tracked_files: list[str]) -> dict[str, tuple[int, int]]:
    """Capture mtime and size for all tracked files."""
    stamps: dict[str, tuple[int, int]] = {}
    for rel_path in tracked_files:
        full_path = repo_root / rel_path
        try:
            st = full_path.stat()
            stamps[rel_path] = (st.st_mtime_ns, st.st_size)
        except OSError:
            pass
    return stamps


def check_config_diff(repo_root: Path, initial_bytes: bytes | None) -> str | None:
    """Detect changes to workspace config.yaml."""
    cfg = repo_root / "config.yaml"
    curr = cfg.read_bytes() if cfg.exists() else None
    if initial_bytes is None and curr is not None:
        return "config.yaml (created by tests)"
    if initial_bytes is not None and curr is None:
        return "config.yaml (deleted by tests)"
    if initial_bytes != curr:
        return "config.yaml (content modified by tests)"
    return None


def is_git_file_modified(repo_root: Path, rel_path: str) -> bool:
    """Check if a tracked file has uncommitted changes relative to the git index.

    git finds the index itself, also in a linked worktree, where `.git` is a file; a git error
    exits non-zero and counts as a change.
    """
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--quiet", "--", rel_path],
            check=False,
            capture_output=True,
        )
        return res.returncode != 0
    except Exception:
        return True


def check_tracked_diff(repo_root: Path, snapshot: dict[str, tuple[int, int]]) -> list[str]:
    """Detect modifications or deletions in git-tracked files."""
    diffs: list[str] = []
    for rel_path, (init_mtime, init_size) in snapshot.items():
        full = repo_root / rel_path
        if not full.exists():
            diffs.append(f"{rel_path} (deleted by tests)")
            continue
        try:
            st = full.stat()
            if (st.st_mtime_ns, st.st_size) != (init_mtime, init_size):
                if is_git_file_modified(repo_root, rel_path):
                    diffs.append(f"{rel_path} (modified by tests)")
        except OSError:
            pass
    return diffs


_FORBIDDEN_PROJECT_TEST_PATHS: tuple[str, ...] = (
    "test_config.yaml",
    "test_data",
    "test_llm_cache",
    "gh-config",
    ".data/test_llm_cache",
)


def check_forbidden_test_paths(repo_root: Path) -> list[str]:
    """Detect explicit test-only paths created in the project repository."""
    diffs: list[str] = []
    for rel in _FORBIDDEN_PROJECT_TEST_PATHS:
        target = repo_root / rel
        if target.exists():
            diffs.append(f"{rel} (test path found in project directory)")
    return diffs


def worker_home_locations(home: Path) -> tuple[Path, ...]:
    """Return the devops-cli locations inside a worker home (#1311)."""
    from devops_cli.config.constants import CONST_APP_NAME

    return (
        home / ".config" / CONST_APP_NAME,
        home / ".local" / "share" / CONST_APP_NAME,
        home / ".ssh",
        home / ".local" / "bin",
    )


def find_location_leaks(loc: Path) -> list[Path]:
    """Find all files or non-empty directories left at *loc* (#1311)."""
    if not loc.exists():
        return []
    if loc.is_file() or loc.is_symlink():
        return [loc]
    entries = sorted(p for p in loc.rglob("*") if not p.is_dir())
    return entries or [loc]


def get_snapshot_homes(snapshot: dict[str, Any]) -> list[Path]:
    """Retrieve list of unique worker home paths recorded during session (#1311)."""
    if "worker_homes" in snapshot:
        return [Path(h) for h in snapshot["worker_homes"]]
    basetemp = snapshot.get("basetemp")
    if not basetemp:
        return []
    reg = Path(basetemp) / ".worker_homes"
    if not reg.exists():
        return []
    return [
        Path(line.strip()) for line in reg.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def check_worker_home_leaks(snapshot: dict[str, Any]) -> list[str]:
    """Detect state left in devops-cli locations within worker homes (#1311)."""
    homes = get_snapshot_homes(snapshot)
    diffs: list[str] = []
    for home in sorted(set(homes)):
        for loc in worker_home_locations(home):
            for leaked in find_location_leaks(loc):
                diffs.append(f"{leaked} (state left in worker home)")
    return diffs


def evaluate_workspace_tripwire(snapshot: dict[str, Any]) -> list[str]:
    """Evaluate all workspace isolation tripwire checks against initial session snapshot."""
    repo_root = snapshot["repo_root"]
    failures: list[str] = []
    cfg_diff = check_config_diff(repo_root, snapshot.get("config_state"))
    if cfg_diff is not None:
        failures.append(cfg_diff)
    failures.extend(check_tracked_diff(repo_root, snapshot.get("tracked_snapshot", {})))
    failures.extend(check_forbidden_test_paths(repo_root))
    failures.extend(check_worker_home_leaks(snapshot))
    return failures


def pytest_sessionstart(session: pytest.Session) -> None:
    """Snapshot workspace config and tracked files on xdist controller."""
    if is_xdist_worker(session.config):
        return
    repo_root = session.config.rootpath
    tracked = get_git_tracked_files(repo_root)
    cfg_path = repo_root / "config.yaml"
    session.config._tripwire_snapshot = {  # type: ignore[attr-defined]
        "repo_root": repo_root,
        "config_state": cfg_path.read_bytes() if cfg_path.exists() else None,
        "tracked_snapshot": snapshot_tracked_files(repo_root, tracked),
        "basetemp": getattr(session.config, "_tripwire_basetemp", None),
    }


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """Verify no tests wrote to workspace config, tracked files, or left test paths."""
    if is_xdist_worker(session.config):
        return
    snapshot = getattr(session.config, "_tripwire_snapshot", None)
    if snapshot is None:
        return
    failures = evaluate_workspace_tripwire(snapshot)
    if failures:
        session.config._tripwire_failures = failures  # type: ignore[attr-defined]
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: Any, exitstatus: Any, config: pytest.Config) -> None:
    """Print prominent error section if test isolation tripwire detected leaks."""
    if is_xdist_worker(config):
        return
    failures = getattr(config, "_tripwire_failures", [])
    if failures:
        terminalreporter.section(
            "TRIPWIRE FAILURE: Workspace mutated during test run", red=True, bold=True
        )
        for f in failures:
            terminalreporter.write_line(f"  - {f}", red=True)
