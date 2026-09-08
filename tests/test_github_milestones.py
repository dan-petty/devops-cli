"""Test suite for GitHub Milestones extraction, synchronization, and progress tracking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.github.milestones import (
    MilestoneProgress,
    MilestoneSpec,
    MilestoneSyncResult,
    calculate_milestone_progress,
    diff_milestones,
    extract_roadmap_milestones,
    sync_repository_milestones,
)


def test_extract_roadmap_milestones(tmp_path: Path) -> None:
    """extract_roadmap_milestones parses markdown milestone headings into MilestoneSpec objects."""
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(
        "# Roadmap\n\n"
        "### Core Foundation (v0.0.1 - Completed)\n"
        "- [x] Feature A\n\n"
        "### Valkey Management (v0.2.12 - Scheduled)\n"
        "- [ ] Task 1\n\n"
        "### Library Ingestion (v0.2.13 - Scheduled)\n"
        "- [ ] Task 2\n",
        encoding="utf-8",
    )

    specs = extract_roadmap_milestones(roadmap)
    assert len(specs) >= 2
    titles = [s.title for s in specs]
    assert "v0.2.12" in titles
    assert "v0.2.13" in titles
    valkey_spec = next(s for s in specs if s.title == "v0.2.12")
    assert valkey_spec.description == "Valkey Management"
    assert "Scheduled" not in valkey_spec.description

    core_spec = next(s for s in specs if s.title == "v0.0.1")
    assert core_spec.description == "Core Foundation"
    assert "Completed" not in core_spec.description
    assert core_spec.state == "closed"


def test_diff_milestones() -> None:
    """diff_milestones correctly detects new, existing, and closed milestones."""
    desired = [
        MilestoneSpec(title="v0.2.12", description="Valkey"),
        MilestoneSpec(title="v0.2.13", description="Library"),
    ]
    existing = [
        {"title": "v0.2.12", "number": 1, "state": "open", "description": "Valkey"},
    ]

    to_create, existing_matches = diff_milestones(desired, existing)
    assert len(to_create) == 1
    assert to_create[0].title == "v0.2.13"
    assert len(existing_matches) == 1
    assert existing_matches[0]["title"] == "v0.2.12"


def test_sync_repository_milestones_dry_run() -> None:
    """Dry-run milestone synchronization simulates creates without sending mutating requests."""
    desired = [
        MilestoneSpec(title="v0.2.15", description="Scanner Framework"),
    ]
    mock_client = MagicMock()
    mock_client.get_milestones.return_value = []

    res = sync_repository_milestones(mock_client, "dan-petty/devops-cli", desired, dry_run=True)
    assert isinstance(res, MilestoneSyncResult)
    assert res.created_count == 1
    assert res.dry_run is True
    mock_client.create_milestone.assert_not_called()


def test_calculate_milestone_progress() -> None:
    """calculate_milestone_progress computes closed ratio and health metrics."""
    data = {
        "title": "v0.2.11",
        "open_issues": 2,
        "closed_issues": 8,
        "state": "open",
    }
    progress = calculate_milestone_progress(data)
    assert isinstance(progress, MilestoneProgress)
    assert progress.total_issues == 10
    assert progress.percent_complete == 80.0
    assert progress.is_complete is False


def test_close_repository_milestone() -> None:
    """close_repository_milestone closes the specified milestone via client."""
    from devops_cli.github.milestones import close_repository_milestone

    mock_client = MagicMock()
    mock_client.close_milestone.return_value = True

    ok = close_repository_milestone(mock_client, "dan-petty/devops-cli", "v0.2.11")
    assert ok is True
    mock_client.close_milestone.assert_called_once_with("dan-petty/devops-cli", "v0.2.11")


def test_close_repository_milestone_single_arg_signature() -> None:
    """close_repository_milestone supports client whose close_milestone takes 1 positional arg."""
    from devops_cli.github.milestones import close_repository_milestone

    class SingleArgClient:
        def close_milestone(self, version_or_title: str) -> bool:
            return version_or_title == "v0.2.11"

    ok = close_repository_milestone(SingleArgClient(), "dan-petty/devops-cli", "v0.2.11")
    assert ok is True


def test_close_repository_milestone_fallback() -> None:
    """close_repository_milestone falls back to get_milestones + edit_milestone."""
    from devops_cli.github.milestones import close_repository_milestone

    mock_client = MagicMock()
    del mock_client.close_milestone
    mock_client.get_milestones.return_value = [{"title": "v0.2.11", "number": 23, "state": "open"}]

    ok = close_repository_milestone(mock_client, "dan-petty/devops-cli", "v0.2.11")
    assert ok is True
    mock_client.edit_milestone.assert_called_once_with("dan-petty/devops-cli", 23, state="closed")


def test_cli_milestones_close_command() -> None:
    """CLI devops gh milestones close executes successfully."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    with patch("devops_cli.commands.gh._get_github_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.close_milestone.return_value = True
        mock_get_client.return_value = mock_client

        res = runner.invoke(
            app, ["milestones", "close", "v0.2.11", "--repo", "dan-petty/devops-cli"]
        )
        assert res.exit_code == 0
        assert "Successfully closed milestone" in res.output


def test_validate_roadmap_path_helpers(tmp_path: Path) -> None:
    """Verify _is_safe_roadmap_path and _validate_roadmap_path prevent directory traversal."""
    import pytest

    from devops_cli.exceptions.git import GitHubOperationError
    from devops_cli.github.milestones import _is_safe_roadmap_path, _validate_roadmap_path

    # Safe vs unsafe path predicates
    assert _is_safe_roadmap_path(Path("docs/ROADMAP.md"))
    assert _is_safe_roadmap_path(Path("docs/ROADMAP..md"))
    assert _is_safe_roadmap_path(tmp_path / "ROADMAP.md")
    assert not _is_safe_roadmap_path(Path("../ROADMAP.md"))
    assert not _is_safe_roadmap_path(Path("docs/../ROADMAP.md"))

    # Traversal raises GitHubOperationError
    with pytest.raises(GitHubOperationError, match="Path traversal detected"):
        _validate_roadmap_path(Path("../ROADMAP.md"))

    with pytest.raises(GitHubOperationError, match="Path traversal detected"):
        _validate_roadmap_path(Path("foo/../bar.md"))

    # Missing file raises GitHubOperationError
    with pytest.raises(GitHubOperationError, match="Roadmap file not found"):
        _validate_roadmap_path(tmp_path / "nonexistent.md")

    # Valid file passes validation
    sample = tmp_path / "valid_roadmap.md"
    sample.write_text("# Roadmap\n", encoding="utf-8")
    assert _validate_roadmap_path(sample) == sample


def test_cli_labels_list() -> None:
    """devops gh labels list prints table of labels or info if empty."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    with patch("devops_cli.commands.gh._get_repo_labels", return_value=[]):
        res = runner.invoke(app, ["labels", "list"])
        assert res.exit_code == 0
        assert "No remote repository labels found" in res.output

    with patch(
        "devops_cli.commands.gh._get_repo_labels",
        return_value=[{"name": "type/bug", "color": "d73a4a", "description": "Bug"}],
    ):
        res = runner.invoke(app, ["labels", "list"])
        assert res.exit_code == 0
        assert "type/bug" in res.output


def test_cli_labels_sync(tmp_path: Path) -> None:
    """devops gh labels sync reconciles labels with dry-run and shim support."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    labels_file = tmp_path / "labels.yml"
    labels_file.write_text(
        "- name: type/bug\n  color: d73a4a\n  description: Defect\n", encoding="utf-8"
    )

    runner = CliRunner()
    with (
        patch("devops_cli.commands.gh._get_github_client", return_value=None),
        patch("devops_cli.commands.gh._get_repo_labels", return_value=[]),
        patch("devops_cli.commands.gh.run_subprocess") as mock_sub,
    ):
        mock_sub.return_value = MagicMock(returncode=0, stdout="")
        res = runner.invoke(app, ["labels", "sync", "--file", str(labels_file), "--dry-run"])
        assert res.exit_code == 0
        assert "DRY RUN" in res.output


def test_cli_labels_audit() -> None:
    """devops gh labels audit detects PRs with missing taxonomy."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    # Compliant PRs
    with patch(
        "devops_cli.commands.gh._get_repo_prs",
        return_value=[
            {
                "number": 1,
                "title": "feat: test",
                "labels": [{"name": "type/feature"}, {"name": "scope/cli"}],
            }
        ],
    ):
        res = runner.invoke(app, ["labels", "audit"])
        assert res.exit_code == 0
        assert "comply with taxonomy" in res.output

    # Non-compliant PRs
    with patch(
        "devops_cli.commands.gh._get_repo_prs",
        return_value=[{"number": 2, "title": "fix: bug", "labels": []}],
    ):
        res = runner.invoke(app, ["labels", "audit"])
        assert res.exit_code == 0
        assert "Pull Request Taxonomy Audit Findings" in res.output


def test_cli_milestones_list() -> None:
    """devops gh milestones list shows empty info or formatted table."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    with patch("devops_cli.commands.gh._get_repo_milestones", return_value=[]):
        res = runner.invoke(app, ["milestones", "list"])
        assert res.exit_code == 0
        assert "No milestones found" in res.output

    with patch(
        "devops_cli.commands.gh._get_repo_milestones",
        return_value=[{"title": "v0.2.13", "state": "open", "open_issues": 1, "closed_issues": 3}],
    ):
        res = runner.invoke(app, ["milestones", "list"])
        assert res.exit_code == 0
        assert "v0.2.13" in res.output


def test_cli_milestones_status() -> None:
    """devops gh milestones status inspects specific milestone."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    with patch(
        "devops_cli.commands.gh._get_repo_milestones",
        return_value=[
            {
                "title": "v0.2.13",
                "state": "open",
                "open_issues": 2,
                "closed_issues": 8,
                "due_on": "2026-09-30",
            }
        ],
    ):
        res = runner.invoke(app, ["milestones", "status", "v0.2.13"])
        assert res.exit_code == 0
        assert "80.0%" in res.output

    with patch("devops_cli.commands.gh._get_repo_milestones", return_value=[]):
        res = runner.invoke(app, ["milestones", "status", "v0.2.13"])
        assert res.exit_code == 1
        assert "not found" in res.output


def test_cli_milestones_sync(tmp_path: Path) -> None:
    """devops gh milestones sync reconciles milestones with roadmap."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text("# Roadmap\n### Test Milestone (v0.9.0 - Scheduled)\n", encoding="utf-8")

    runner = CliRunner()
    with (
        patch("devops_cli.commands.gh._get_github_client", return_value=None),
        patch("devops_cli.commands.gh._get_repo_milestones", return_value=[]),
        patch("devops_cli.commands.gh.run_subprocess") as mock_sub,
    ):
        mock_sub.return_value = MagicMock(returncode=0, stdout="")
        res = runner.invoke(app, ["milestones", "sync", "--roadmap", str(roadmap), "--dry-run"])
        assert res.exit_code == 0
        assert "Milestone synchronization" in res.output


def test_close_milestone_gh_cli() -> None:
    """_close_milestone_gh_cli handles CLI fallback to close milestone."""
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.gh import _close_milestone_gh_cli

    with (
        patch(
            "devops_cli.commands.gh._get_repo_milestones",
            return_value=[{"title": "v0.2.11", "number": 42}],
        ),
        patch("devops_cli.commands.gh.run_subprocess") as mock_sub,
    ):
        mock_sub.return_value = MagicMock(returncode=0)
        ok = _close_milestone_gh_cli("dan-petty/devops-cli", "v0.2.11")
        assert ok is True

    with patch("devops_cli.commands.gh._get_repo_milestones", return_value=[]):
        ok = _close_milestone_gh_cli("dan-petty/devops-cli", "v9.9.9")
        assert ok is False


def test_gh_helper_subprocess_fallbacks() -> None:
    """Test _get_repo_labels, _get_repo_milestones, _get_repo_prs with subprocess JSON output."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.gh import _get_repo_labels, _get_repo_milestones, _get_repo_prs

    with patch("devops_cli.commands.gh.run_subprocess") as mock_sub:
        # labels
        mock_sub.return_value = MagicMock(returncode=0, stdout=json.dumps([{"name": "test"}]))
        assert len(_get_repo_labels("dan-petty/devops-cli")) == 1

        # milestones
        mock_sub.return_value = MagicMock(
            returncode=0, stdout=json.dumps([{"title": "v1.0", "number": 1}])
        )
        assert len(_get_repo_milestones("dan-petty/devops-cli")) == 1

        # prs
        mock_sub.return_value = MagicMock(
            returncode=0, stdout=json.dumps([{"number": 10, "title": "feat: test"}])
        )
        assert len(_get_repo_prs("dan-petty/devops-cli")) == 1
