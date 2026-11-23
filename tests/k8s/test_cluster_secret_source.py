"""Tests that environment Secret rows are removed from code (#6685)."""

from __future__ import annotations

import subprocess

from tests.support.paths import REPO_ROOT


def test_no_moved_stack_rows_remain() -> None:
    """The module cluster_secrets.py MUST contain no environment Secret rows after the change."""
    res = subprocess.run(
        ["git", "grep", "-n", "-E", 'stack=(BASE_STACK|"(chat|gitea|infra)")', "src/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1, f"Found moved stack rows in src/:\n{res.stdout}"
    assert res.stdout == ""


def test_only_product_valkey_rows_remain() -> None:
    """The only llm rows left in cluster_secrets.py are valkey-devops-auth and valkey-runs-auth."""
    res = subprocess.run(
        ["git", "grep", "-n", 'name="valkey-', "src/devops_cli/k8s/cluster_secrets.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 2, f"Expected 2 valkey rows, got:\n{res.stdout}"
    assert any('name="valkey-devops-auth"' in line for line in lines)
    assert any('name="valkey-runs-auth"' in line for line in lines)
