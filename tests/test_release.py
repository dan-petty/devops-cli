"""Unit tests for devops release subcommands."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.release import (
    _extract_changelog_notes,
    _get_init_version,
    _get_latest_changelog_version,
    _get_pyproject_version,
    _resolve_safe_project_path,
    _update_changelog_header,
    _update_init_version,
    _update_pyproject_version,
    app,
)

runner = CliRunner()


@pytest.fixture
def sample_project_dir(tmp_path: Path) -> Path:
    """Create a mock repository root with pyproject.toml, __init__.py, and CHANGELOG.md."""
    src_dir = tmp_path / "src" / "devops_cli"
    src_dir.mkdir(parents=True)

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "devops-cli"\nversion = "0.1.7"\n',
        encoding="utf-8",
    )

    init_file = src_dir / "__init__.py"
    init_file.write_text(
        '"""DevOps CLI package."""\n__version__ = "0.1.7"\n',
        encoding="utf-8",
    )

    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_content = (
        "# Changelog\n\n"
        "## [0.1.7] - 2026-08-13\n\n"
        "### Added\n- Native DevContainer Lifecycle.\n\n"
        "## [0.1.6] - 2026-08-12\n\n"
        "### Added\n- Initial feature.\n"
    )
    changelog_file.write_text(changelog_content, encoding="utf-8")

    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")

    return tmp_path


def test_get_versions_and_notes(sample_project_dir: Path) -> None:
    assert _get_pyproject_version(sample_project_dir) == "0.1.7"
    assert _get_init_version(sample_project_dir) == "0.1.7"
    assert _get_latest_changelog_version(sample_project_dir) == "0.1.7"

    notes = _extract_changelog_notes(sample_project_dir, "0.1.7")
    assert notes is not None
    assert "Native DevContainer Lifecycle" in notes


def test_update_versions(sample_project_dir: Path) -> None:
    assert _update_pyproject_version(sample_project_dir, "0.1.8")
    assert _get_pyproject_version(sample_project_dir) == "0.1.8"

    assert _update_init_version(sample_project_dir, "0.1.8")
    assert _get_init_version(sample_project_dir) == "0.1.8"

    assert _update_changelog_header(sample_project_dir, "0.1.8", "2026-08-17")
    assert _get_latest_changelog_version(sample_project_dir) == "0.1.8"


def test_release_status_command(sample_project_dir: Path) -> None:
    with patch("devops_cli.commands.release.DocGenerator.check_docs", return_value=(True, [])):
        result = runner.invoke(app, ["status", "--root", str(sample_project_dir)])
        assert result.exit_code == 0
        assert "DevOps CLI Release Status" in result.output
        assert "0.1.7" in result.output


def test_release_prepare_invalid_version(sample_project_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["prepare", "invalid-version-string", "--root", str(sample_project_dir)],
    )
    assert result.exit_code == 1
    assert "Invalid semantic version" in result.output


def test_release_prepare_dry_run(sample_project_dir: Path) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        result = runner.invoke(app, ["prepare", "0.1.8", "--root", str(sample_project_dir)])
        assert result.exit_code == 0
        assert "prepare_release_version" in result.output
        assert '"dry_run": true' in result.output
        assert _get_pyproject_version(sample_project_dir) == "0.1.7"
    finally:
        set_dry_run(False)


def test_release_prepare_success(sample_project_dir: Path) -> None:
    with patch("devops_cli.commands.release.DocGenerator.write_all_docs") as mock_gen:
        result = runner.invoke(
            app,
            ["prepare", "0.1.8", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert _get_pyproject_version(sample_project_dir) == "0.1.8"
        assert _get_init_version(sample_project_dir) == "0.1.8"
        mock_gen.assert_called_once()


def test_release_check_success(sample_project_dir: Path) -> None:
    with (
        patch("devops_cli.commands.release._is_git_clean", return_value=True),
        patch("devops_cli.commands.release.DocGenerator.check_docs", return_value=(True, [])),
        patch("devops_cli.commands.release.run_subprocess") as mock_sub,
    ):
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["uv", "run", "devops", "ci", "run"],
            returncode=0,
            stdout="All checks passed!",
            stderr="",
        )
        result = runner.invoke(app, ["check", "--root", str(sample_project_dir)])
        assert result.exit_code == 0
        assert "All release verification checks passed" in result.output


def test_release_check_version_mismatch(sample_project_dir: Path) -> None:
    _update_pyproject_version(sample_project_dir, "0.1.8")
    result = runner.invoke(
        app,
        ["check", "--root", str(sample_project_dir), "--allow-dirty"],
    )
    assert result.exit_code == 1
    assert "Version mismatch" in result.output


def test_release_check_dirty_repo(sample_project_dir: Path) -> None:
    with patch("devops_cli.commands.release._is_git_clean", return_value=False):
        result = runner.invoke(app, ["check", "--root", str(sample_project_dir)])
        assert result.exit_code == 1
        assert "Git working directory is dirty" in result.output


def test_release_notes_command(sample_project_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["notes", "--version", "0.1.7", "--root", str(sample_project_dir)],
    )
    assert result.exit_code == 0
    assert "Native DevContainer Lifecycle" in result.output


def test_release_notes_raw_command(sample_project_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["notes", "--version", "0.1.7", "--raw", "--root", str(sample_project_dir)],
    )
    assert result.exit_code == 0
    assert "### Added" in result.output
    assert "Native DevContainer Lifecycle" in result.output
    assert "╭" not in result.output


def test_release_notes_dry_run(sample_project_dir: Path) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        result = runner.invoke(
            app,
            ["notes", "--version", "0.1.7", "--raw", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert "extract_release_notes" in result.output
        assert '"dry_run": true' in result.output
    finally:
        set_dry_run(False)


def test_release_tag_command(sample_project_dir: Path) -> None:
    with patch("devops_cli.commands.release.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["git", "tag"],
            returncode=0,
            stdout="",
            stderr="",
        )
        result = runner.invoke(
            app,
            ["tag", "--version", "0.1.7", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert "Created git tag" in result.output


def test_release_pr_dry_run(sample_project_dir: Path) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        result = runner.invoke(
            app,
            ["pr", "--version", "0.1.8", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert "create_release_pull_request" in result.output
        assert '"dry_run": true' in result.output
        assert "release/v0.1.8" in result.output
    finally:
        set_dry_run(False)


def test_release_pr_command(sample_project_dir: Path) -> None:
    with patch("devops_cli.commands.release.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/your-org/devops-cli/pull/42\n",
            stderr="",
        )
        result = runner.invoke(
            app,
            ["pr", "--version", "0.1.8", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert "Created Release Pull Request" in result.output
        assert "pull/42" in result.output


def test_format_release_title() -> None:
    from devops_cli.commands.release import _format_release_title

    assert _format_release_title("0.1.8", prefix="feat") == "feat(release): v0.1.8"
    assert _format_release_title("v0.1.8", prefix="fix") == "fix(release): v0.1.8"
    assert _format_release_title("1.0.0", prefix="feat", breaking=True) == "feat(release)!: v1.0.0"
    assert _format_release_title("1.0.1", prefix="fix", breaking=True) == "fix(release)!: v1.0.1"
    assert _format_release_title("0.2.0", prefix="other") == "feat(release): v0.2.0"


def test_release_pr_conventional_flags(sample_project_dir: Path) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        result = runner.invoke(
            app,
            [
                "pr",
                "--version",
                "0.1.8",
                "--type",
                "fix",
                "--breaking",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert result.exit_code == 0
        assert "fix(release)!: v0.1.8" in result.output
    finally:
        set_dry_run(False)


def test_resolve_safe_project_path(sample_project_dir: Path) -> None:
    # Valid relative paths within repo
    safe_path = _resolve_safe_project_path(sample_project_dir, "CHANGELOG.md")
    assert safe_path == sample_project_dir / "CHANGELOG.md"

    init_rel_path = Path("src/devops_cli/__init__.py")
    safe_sub_path = _resolve_safe_project_path(sample_project_dir, init_rel_path)
    assert safe_sub_path == sample_project_dir / "src" / "devops_cli" / "__init__.py"

    # Malicious traversal attempts outside repo root
    with pytest.raises(ValueError, match="Path traversal detected"):
        _resolve_safe_project_path(sample_project_dir, "../../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        _resolve_safe_project_path(sample_project_dir, Path("..") / "sibling_repo" / "file.txt")
