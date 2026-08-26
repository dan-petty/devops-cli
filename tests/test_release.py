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


def test_release_check_command(sample_project_dir: Path) -> None:
    """Verify devops release check subcommand."""
    # Dry run
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        with (
            patch("devops_cli.commands.release._is_git_clean", return_value=True),
            patch("devops_cli.commands.release.DocGenerator.check_docs", return_value=(True, [])),
        ):
            res_dry = runner.invoke(app, ["check", "--root", str(sample_project_dir)])
            assert res_dry.exit_code == 0
            assert "verify_release_readiness" in res_dry.output
    finally:
        set_dry_run(False)

    # Docs out of sync
    with (
        patch("devops_cli.commands.release._is_git_clean", return_value=True),
        patch(
            "devops_cli.commands.release.DocGenerator.check_docs",
            return_value=(False, ["README diff"]),
        ),
    ):
        res_docs_err = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--skip-ci"])
        assert res_docs_err.exit_code == 1

    # CI failure
    mock_ci_fail = subprocess.CompletedProcess(
        args=["ci"], returncode=1, stdout="", stderr="Lint error"
    )
    with (
        patch("devops_cli.commands.release._is_git_clean", return_value=True),
        patch("devops_cli.commands.release.DocGenerator.check_docs", return_value=(True, [])),
        patch("devops_cli.commands.release.run_subprocess", return_value=mock_ci_fail),
    ):
        res_ci_fail = runner.invoke(app, ["check", "--root", str(sample_project_dir)])
        assert res_ci_fail.exit_code == 1


def test_release_notes_raw_and_missing(sample_project_dir: Path) -> None:
    """Verify devops release notes subcommand."""
    # Normal and raw
    res_raw = runner.invoke(
        app, ["notes", "--version", "0.1.7", "--raw", "--root", str(sample_project_dir)]
    )
    assert res_raw.exit_code == 0
    assert "Native DevContainer Lifecycle" in res_raw.output

    # Missing version notes
    res_no_notes = runner.invoke(
        app, ["notes", "--version", "9.9.9", "--root", str(sample_project_dir)]
    )
    assert res_no_notes.exit_code == 1


def test_release_tag_push_and_errors(sample_project_dir: Path) -> None:
    """Verify devops release tag push and error branches."""
    # Dry run
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res_tag_dry = runner.invoke(
            app, ["tag", "--version", "0.1.7", "--push", "--root", str(sample_project_dir)]
        )
        assert res_tag_dry.exit_code == 0
        assert "create_annotated_git_tag" in res_tag_dry.output
    finally:
        set_dry_run(False)

    # Invalid version
    res_inv = runner.invoke(
        app, ["tag", "--version", "not-a-semver", "--root", str(sample_project_dir)]
    )
    assert res_inv.exit_code == 1

    # Push tags success
    mock_ok = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
    with patch("devops_cli.commands.release.run_subprocess", return_value=mock_ok):
        res_push = runner.invoke(
            app, ["tag", "--version", "0.1.7", "--push", "--root", str(sample_project_dir)]
        )
        assert res_push.exit_code == 0


def test_release_pr_labels_and_draft(sample_project_dir: Path) -> None:
    """Verify devops release pr label validation and draft options."""

    def mock_subproc(cmd, *args, **kwargs):
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="https://github.com/org/repo/pull/1\n", stderr=""
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_subprocess", side_effect=mock_subproc):
        res_bad_lbl = runner.invoke(
            app,
            [
                "pr",
                "--version",
                "0.1.8",
                "--labels",
                "bad;label",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert res_bad_lbl.exit_code == 1
        assert "Invalid label" in res_bad_lbl.output

        res_pr_ok = runner.invoke(
            app,
            [
                "pr",
                "--version",
                "0.1.8",
                "--labels",
                "release, automated",
                "--draft",
                "--push",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert res_pr_ok.exit_code == 0
        assert "Created Release Pull Request" in res_pr_ok.output

        # Release check command
        with patch("devops_cli.docs.generator.DocGenerator.check_docs", return_value=(True, [])):
            res_check = runner.invoke(
                app, ["check", "--skip-ci", "--allow-dirty", "--root", str(sample_project_dir)]
            )
            assert res_check.exit_code == 0
            assert "release verification checks passed" in res_check.output.lower()


def test_release_pr_error_branches_and_breaking(sample_project_dir: Path) -> None:
    """Verify release pr branch failure, breaking flag, and gh create failure."""
    # 1. Branch checkout failure
    with patch(
        "devops_cli.commands.release.run_subprocess",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="git checkout error"
        ),
    ):
        res_br_fail = runner.invoke(
            app, ["pr", "--version", "0.1.8", "--root", str(sample_project_dir)]
        )
        assert res_br_fail.exit_code == 1

    # 2. Breaking change PR
    def mock_breaking_subproc(cmd, *args, **kwargs):
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="https://github.com/org/repo/pull/2\n", stderr=""
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_subprocess", side_effect=mock_breaking_subproc):
        res_breaking = runner.invoke(
            app,
            [
                "pr",
                "--version",
                "1.0.0",
                "--breaking",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert res_breaking.exit_code == 0
        assert "Created Release Pull Request" in res_breaking.output

    # 3. gh pr create failure
    def mock_gh_fail_subproc(cmd, *args, **kwargs):
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="gh: authentication required"
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_subprocess", side_effect=mock_gh_fail_subproc):
        res_gh_fail = runner.invoke(
            app, ["pr", "--version", "0.1.8", "--root", str(sample_project_dir)]
        )
        assert res_gh_fail.exit_code == 0
        assert (
            "authentication required" in res_gh_fail.output
            or "Could not open PR" in res_gh_fail.output
        )


def test_release_notes_tag_and_check_extended(sample_project_dir: Path) -> None:
    """Verify release notes formatting, tag creation/pushing, and check mismatch errors."""
    # 1. release notes raw and formatted
    res_notes_raw = runner.invoke(
        app, ["notes", "--version", "0.1.7", "--raw", "--root", str(sample_project_dir)]
    )
    assert res_notes_raw.exit_code == 0
    assert "Added" in res_notes_raw.output

    res_notes_panel = runner.invoke(
        app, ["notes", "--version", "0.1.7", "--root", str(sample_project_dir)]
    )
    assert res_notes_panel.exit_code == 0
    assert "Release Notes" in res_notes_panel.output

    res_notes_missing = runner.invoke(
        app, ["notes", "--version", "9.9.9", "--root", str(sample_project_dir)]
    )
    assert res_notes_missing.exit_code == 1

    # 2. release tag invalid version and dry run
    res_tag_bad = runner.invoke(
        app, ["tag", "--version", "bad-version", "--root", str(sample_project_dir)]
    )
    assert res_tag_bad.exit_code == 1

    with patch("devops_cli.commands.release.is_dry_run", return_value=True):
        res_tag_dry = runner.invoke(
            app, ["tag", "--version", "0.1.8", "--root", str(sample_project_dir)]
        )
        assert res_tag_dry.exit_code == 0

    # 3. release tag execution and push
    called_cmds = []

    def mock_tag_subproc(cmd, *args, **kwargs):
        called_cmds.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_subprocess", side_effect=mock_tag_subproc):
        res_tag_ok = runner.invoke(
            app, ["tag", "--version", "0.1.8", "--push", "--root", str(sample_project_dir)]
        )
        assert res_tag_ok.exit_code == 0
        assert any("tag" in c and "-a" in c and "v0.1.8" in c for c in called_cmds)
        assert any("push" in c and "--tags" in c for c in called_cmds)

    # 4. release check version mismatch
    pyproject_file = sample_project_dir / "pyproject.toml"
    pyproject_file.write_text('[project]\nname = "test"\nversion = "0.9.0"\n', encoding="utf-8")

    res_mismatch = runner.invoke(app, ["check", "--root", str(sample_project_dir)])
    assert res_mismatch.exit_code == 1
    assert "Version mismatch" in res_mismatch.output
