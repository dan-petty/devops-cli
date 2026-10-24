"""Tests for the diff-quality CI quality gate check (#423).

A diff-quality row in `devops ci` fails any changed line that adds a violation of
C901, BLE001, S110, S112, E402, F401, SIM115, UP036 or N803, using --ignore-noqa.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import app, get_check_spec, get_check_specs
from devops_cli.dry_run import set_dry_run
from tests.support.paths import REPO_ROOT

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_dry_run_state() -> None:
    """Ensure dry-run state is clean before and after each test."""
    set_dry_run(False)
    yield
    set_dry_run(False)


def _init_git_repo(path: Path) -> None:
    """Initialize a git repository under path with an initial commit on main."""
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    initial_file = path / "initial.py"
    initial_file.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, check=True)


def test_diff_quality_check_spec_registered() -> None:
    """diff-quality check specification is registered with required rules and options."""
    specs = {s.name: s for s in get_check_specs()}
    assert "diff-quality" in specs
    spec = get_check_spec("diff-quality")
    cmd_str = " ".join(spec.cmd)

    assert "diff-quality" in cmd_str
    assert "--violations ruff.check" in cmd_str
    assert "--fail-under 100" in cmd_str
    assert "--ignore-noqa" in cmd_str
    for rule in ("C901", "BLE001", "S110", "S112", "E402", "F401", "SIM115", "UP036", "N803"):
        assert rule in cmd_str


def test_diff_quality_dry_run() -> None:
    """devops ci diff-quality --dry-run prints a one-request plan and starts zero processes."""
    res = runner.invoke(app, ["diff-quality", "--dry-run"])
    assert res.exit_code == 0
    assert "diff-quality" in res.stdout
    assert "--violations" in res.stdout
    assert "ruff.check" in res.stdout


@pytest.mark.live("uv", "diff-quality", "ruff")
def test_diff_quality_gate_fails_blind_except_and_over_cap_c901(tmp_path: Path) -> None:
    """In a git repo, a new except Exception: fails, a new # noqa: C901 fails, and compliant code passes."""
    venv_bin = REPO_ROOT / ".venv" / "bin"
    env = dict(os.environ)
    if venv_bin.is_dir():
        env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"

    if not shutil.which("diff-quality", path=env["PATH"]) and not shutil.which(
        "uv", path=env["PATH"]
    ):
        pytest.skip("diff-quality and ruff must be available in PATH for live test")

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    spec = get_check_spec("diff-quality")
    cmd = list(spec.cmd)
    # Ensure --compare-branch=main is passed for local test repo without origin/main
    cmd = [c for c in cmd if not c.startswith("--compare-branch=")]
    cmd.append("--compare-branch=main")

    # 1. Branch with new except Exception: (even with noqa: BLE001)
    subprocess.run(["git", "checkout", "-b", "blind-except"], cwd=repo_dir, check=True)
    bad_file = repo_dir / "bad_except.py"
    bad_file.write_text(
        "try:\n    pass\nexcept Exception:  " + "# noqa: BLE001\n    pass\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Add blind except"], cwd=repo_dir, check=True)

    res_except = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, env=env)
    assert res_except.returncode != 0, (
        f"Expected failure for blind except, but passed:\n{res_except.stdout}"
    )
    assert "BLE001" in res_except.stdout or "S110" in res_except.stdout

    # 2. Branch with new function exceeding C901 complexity cap (even with noqa: C901)
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "checkout", "-b", "complex-func"], cwd=repo_dir, check=True)
    complex_file = repo_dir / "complex.py"
    branches = "\n".join(f"    if x == {i}: return {i}" for i in range(12))
    complex_file.write_text(
        "def complex_func(x: int) -> int:  " + "# noqa: C901\n" + f"{branches}\n    return 0\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Add complex function"], cwd=repo_dir, check=True)

    res_c901 = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, env=env)
    assert res_c901.returncode != 0, (
        f"Expected failure for C901 over-cap function, but passed:\n{res_c901.stdout}"
    )
    assert "C901" in res_c901.stdout

    # 3. Branch with clean, compliant code
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "checkout", "-b", "clean-feature"], cwd=repo_dir, check=True)
    clean_file = repo_dir / "clean.py"
    clean_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Add clean code"], cwd=repo_dir, check=True)

    res_clean = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, env=env)
    assert res_clean.returncode == 0, (
        f"Expected success for compliant code, but failed:\n{res_clean.stdout}\n{res_clean.stderr}"
    )
