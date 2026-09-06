"""Test suite for declarative GitHub Labels management and synchronization."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.github.labels import (
    LabelSpec,
    LabelSyncResult,
    audit_repository_labels,
    diff_labels,
    load_label_specs,
    sync_repository_labels,
)


def test_load_label_specs_from_yaml(tmp_path: Path) -> None:
    """Label specs are properly deserialized from YAML into validated Pydantic models."""
    sample_yaml = tmp_path / "labels.yml"
    sample_yaml.write_text(
        "- name: 'type/feature'\n"
        "  color: '0E8A16'\n"
        "  description: 'New feature addition'\n"
        "- name: 'scope/ai'\n"
        "  color: '6F42C1'\n"
        "  description: 'AI review engine'\n",
        encoding="utf-8",
    )

    specs = load_label_specs(sample_yaml)
    assert len(specs) == 2
    assert specs[0].name == "type/feature"
    assert specs[0].color == "0E8A16"
    assert specs[1].name == "scope/ai"


def test_diff_labels_identifies_creates_and_updates() -> None:
    """diff_labels correctly partitions specs into new, updated, and unchanged labels."""
    desired = [
        LabelSpec(name="type/bug", color="D73A4A", description="Defect"),
        LabelSpec(
            name="type/docs", color="0075CA", description="Updated documentation description"
        ),
        LabelSpec(name="type/infra", color="5319E7", description="Infrastructure"),
    ]
    existing = [
        {"name": "type/bug", "color": "D73A4A", "description": "Defect"},
        {"name": "type/docs", "color": "000000", "description": "Old docs"},  # color & desc differ
    ]

    to_create, to_update, unchanged = diff_labels(desired, existing)
    assert len(to_create) == 1
    assert to_create[0].name == "type/infra"
    assert len(to_update) == 1
    assert to_update[0].name == "type/docs"
    assert len(unchanged) == 1
    assert unchanged[0].name == "type/bug"


def test_sync_repository_labels_dry_run() -> None:
    """Dry-run label synchronization previews changes without invoking mutating API calls."""
    desired = [
        LabelSpec(name="type/security", color="B60205", description="Security issue"),
    ]
    mock_client = MagicMock()
    mock_client.get_labels.return_value = []

    res = sync_repository_labels(mock_client, "dan-petty/devops-cli", desired, dry_run=True)
    assert isinstance(res, LabelSyncResult)
    assert res.created_count == 1
    assert res.dry_run is True
    mock_client.create_label.assert_not_called()


def test_audit_repository_labels() -> None:
    """audit_repository_labels flags pull requests missing type/ or scope/ taxonomy labels."""
    sample_prs = [
        {
            "number": 10,
            "title": "feat: add feature",
            "labels": [{"name": "type/feature"}],
        },  # Missing scope
        {
            "number": 11,
            "title": "fix: fix bug",
            "labels": [{"name": "type/bug"}, {"name": "scope/k8s"}],
        },  # Valid
        {"number": 12, "title": "chore: cleanup", "labels": []},  # Missing both
    ]

    findings = audit_repository_labels(sample_prs)
    assert len(findings) == 2
    assert findings[0].pr_number == 10
    assert "Missing scope label" in findings[0].issue
    assert findings[1].pr_number == 12
