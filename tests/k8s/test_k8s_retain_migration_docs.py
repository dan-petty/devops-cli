"""Tests for Local-Path Retain Migration runbook in k8s/README.md."""

from __future__ import annotations

import re

from tests.support.paths import REPO_ROOT

README_PATH = REPO_ROOT / "k8s" / "README.md"


def test_retain_migration_section_exists_and_order() -> None:
    """Assert the Local-Path Retain Migration section exists and steps are ordered."""
    content = README_PATH.read_text(encoding="utf-8")
    assert "Local-Path Retain Migration" in content

    match = re.search(r"#+\s+Local-Path Retain Migration.*?(?=\n## |\Z)", content, re.DOTALL)
    assert match is not None, "Section 'Local-Path Retain Migration' not found"
    section = match.group(0)

    patch_pos = section.find("kubectl patch pv")
    delete_pos = section.find("kubectl delete statefulset")

    assert patch_pos != -1, "kubectl patch pv not found in section"
    assert delete_pos != -1, "kubectl delete statefulset not found in section"
    assert patch_pos < delete_pos, "kubectl patch pv must come before kubectl delete statefulset"


def test_retain_migration_patch_and_listing_commands() -> None:
    """Assert exact patch command and get pv listing command exist in section."""
    content = README_PATH.read_text(encoding="utf-8")
    match = re.search(r"#+\s+Local-Path Retain Migration.*?(?=\n## |\Z)", content, re.DOTALL)
    assert match is not None
    section = match.group(0)

    exact_patch = (
        'kubectl patch pv <name> -p \'{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}\''
    )
    assert exact_patch in section, f"Exact patch command not found: {exact_patch}"

    assert "kubectl get pv" in section
    assert "persistentVolumeReclaimPolicy" in section
    assert "Delete" in section


def test_retain_migration_statefulset_recreation_command() -> None:
    """Assert exact delete statefulset command and wait verification command exist."""
    content = README_PATH.read_text(encoding="utf-8")
    match = re.search(r"#+\s+Local-Path Retain Migration.*?(?=\n## |\Z)", content, re.DOTALL)
    assert match is not None
    section = match.group(0)

    exact_delete = "kubectl delete statefulset <name> --cascade=orphan"
    assert exact_delete in section, f"Exact delete command not found: {exact_delete}"

    assert "kubectl rollout status statefulset <name>" in section or "kubectl wait" in section
    assert "Ready" in section
