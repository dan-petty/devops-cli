"""Unit tests for devops release subcommands."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
import yaml
from typer.testing import CliRunner

from devops_cli.commands.release import (
    _extract_changelog_notes,
    _extract_git_commit_notes,
    _get_init_version,
    _get_latest_changelog_version,
    _get_project_root,
    _get_pyproject_version,
    _release_paths,
    _resolve_safe_project_path,
    _update_changelog_header,
    _update_init_version,
    _update_pyproject_version,
    _verify_release_versions,
    app,
)
from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GIT_NO_TERMINAL_PROMPT_ENV,
    CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS,
    CONST_GITHUB_RELEASE_BODY_MAX_CHARS,
)
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitOperationError,
    ReleaseBranchMissingError,
    ReleasePRCreationError,
    ReleasePushError,
    ReleasePushRefusedError,
    ReleaseRemoteFetchError,
    ReleaseWorkingTreeDirtyError,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState
from tests.conftest import PINNED_GITHUB_TOKEN, fail_the_github_lookup
from tests.release_notes_examples import (
    SYNTHETIC_CATEGORIES,
    SYNTHETIC_ENTRY_COUNT,
    synthetic_entry_detail,
    synthetic_entry_title,
    synthetic_release_section,
)

runner = CliRunner()
# A Markdown task-list item, ticked or not, under any list marker and at any indent.
_CHECKBOX_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\]", re.MULTILINE)


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


def test_dynamic_init_version_handling(tmp_path: Path) -> None:
    """Verify release functions handle dynamic __version__ without overwriting __init__.py."""
    src_dir = tmp_path / "src" / "devops_cli"
    src_dir.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "devops-cli"\nversion = "0.2.0"\n',
        encoding="utf-8",
    )
    init_file = src_dir / "__init__.py"
    init_code = (
        "from devops_cli.config.metadata import get_version\n\n__version__ = get_version()\n"
    )
    init_file.write_text(init_code, encoding="utf-8")

    initial_init_ver = _get_init_version(tmp_path)
    update_init_res = _update_init_version(tmp_path, "0.2.1")
    init_content_after = init_file.read_text(encoding="utf-8")

    update_pyproject_res = _update_pyproject_version(tmp_path, "0.2.1")
    pyproject_ver_after = _get_pyproject_version(tmp_path)
    init_ver_after = _get_init_version(tmp_path)

    assert (
        initial_init_ver,
        update_init_res,
        init_content_after,
        update_pyproject_res,
        pyproject_ver_after,
        init_ver_after,
    ) == (
        "0.2.0",
        True,
        init_code,
        True,
        "0.2.1",
        "0.2.1",
    )


def test_missing_init_version_handling(tmp_path: Path) -> None:
    """Verify release functions return None/False when __init__.py lacks __version__."""
    src_dir = tmp_path / "src" / "devops_cli"
    src_dir.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "devops-cli"\nversion = "0.2.0"\n',
        encoding="utf-8",
    )
    init_file = src_dir / "__init__.py"
    init_file.write_text('"""Package without version."""\n', encoding="utf-8")

    get_res = _get_init_version(tmp_path)
    update_res = _update_init_version(tmp_path, "0.2.1")
    assert (get_res, update_res) == (None, False)


def test_release_status_command(sample_project_dir: Path) -> None:
    with patch("devops_cli.commands.release.DocGenerator.check_docs", return_value=(True, [])):
        result = runner.invoke(app, ["status", "--root", str(sample_project_dir)])
        assert result.exit_code == 0
        assert "DevOps CLI Release Status" in result.output
        assert "0.1.7" in result.output


def test_release_status_watch(sample_project_dir: Path) -> None:
    with patch("devops_cli.commands.release.DocGenerator.check_docs", return_value=(True, [])):
        with patch("devops_cli.watchers.live_resource.LiveResourceWatcher.watch") as mock_watch:
            result = runner.invoke(
                app,
                [
                    "status",
                    "--root",
                    str(sample_project_dir),
                    "--watch",
                    "--interval",
                    "1.0",
                ],
            )
            assert result.exit_code == 0
            assert mock_watch.called


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
        patch(
            "devops_cli.commands.release.DocGenerator.check_docs",
            return_value=(True, []),
        ),
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


def _write_runtime_kustomization(root: Path, tag: str) -> Path:
    path = root / "k8s" / "devops" / "kustomization.yaml"
    path.parent.mkdir(parents=True)
    document = {
        "resources": ["cronjob.yaml"],
        "images": [{"name": "ghcr.io/dan-petty/devops-cli/service", "newTag": tag}],
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_release_prepare_pins_the_service_image_to_the_new_version(
    sample_project_dir: Path,
) -> None:
    path = _write_runtime_kustomization(sample_project_dir, "v0.1.7")
    with patch("devops_cli.commands.release.DocGenerator.write_all_docs"):
        result = runner.invoke(app, ["prepare", "0.1.8", "--root", str(sample_project_dir)])
    images = yaml.safe_load(path.read_text(encoding="utf-8"))["images"]
    assert (result.exit_code, images[0]["newTag"]) == (0, "v0.1.8")


def test_release_paths_stage_the_runtime_kustomization(tmp_path: Path) -> None:
    _write_runtime_kustomization(tmp_path, "v0.1.7")
    assert "k8s/devops/kustomization.yaml" in _release_paths(tmp_path)


def test_release_check_fails_when_the_service_image_tag_is_out_of_step(
    sample_project_dir: Path,
) -> None:
    _write_runtime_kustomization(sample_project_dir, "v0.1.6")
    result = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--allow-dirty"])
    output = " ".join(result.output.split())
    assert (result.exit_code, "k8s/devops/kustomization.yaml pins" in output) == (
        1,
        True,
    )


def _write_argocd_application(
    root: Path,
    name: str = "test-app",
    git_revision: str = "main",
    chart_revision: str = "1.2.3",
) -> Path:
    path = root / "k8s" / "argocd" / "apps" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {
            "project": "default",
            "sources": [
                {
                    "repoURL": "https://charts.example.com",
                    "chart": "test-chart",
                    "targetRevision": chart_revision,
                },
                {
                    "repoURL": "https://github.com/dan-petty/devops-cli",
                    "targetRevision": git_revision,
                    "path": "k8s/test",
                },
            ],
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "test",
            },
        },
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def test_release_paths_stage_argocd(tmp_path: Path) -> None:
    _write_argocd_application(tmp_path)
    assert "k8s/argocd/" in _release_paths(tmp_path)


def test_release_prepare_rewrites_argocd_target_revisions(
    sample_project_dir: Path,
) -> None:
    app_path = _write_argocd_application(sample_project_dir, git_revision="release/v0.1.7")
    with patch("devops_cli.commands.release.DocGenerator.write_all_docs"):
        result = runner.invoke(app, ["prepare", "0.1.8", "--root", str(sample_project_dir)])
    assert result.exit_code == 0
    doc = yaml.safe_load(app_path.read_text(encoding="utf-8"))
    sources = doc["spec"]["sources"]
    assert (sources[0]["targetRevision"], sources[1]["targetRevision"]) == (
        "1.2.3",
        "main",
    )


def test_release_check_fails_on_mismatched_argocd_target_revisions(
    sample_project_dir: Path,
) -> None:
    _write_argocd_application(sample_project_dir, name="app1", git_revision="main")
    _write_argocd_application(sample_project_dir, name="app2", git_revision="release/v0.1.8")
    result = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--allow-dirty"])
    assert (result.exit_code, "Argo CD git-source targetRevisions mismatch" in result.output) == (
        1,
        True,
    )


def test_release_check_fails_on_argocd_target_revision_not_matching_main(
    sample_project_dir: Path,
) -> None:
    _write_argocd_application(sample_project_dir, git_revision="release/v0.1.6")
    result = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--allow-dirty"])
    assert (
        result.exit_code,
        "does not match expected 'main'" in result.output,
    ) == (1, True)


def test_release_check_succeeds_with_matching_argocd_target_revisions(
    sample_project_dir: Path,
) -> None:
    _write_argocd_application(sample_project_dir, git_revision="main")
    with (
        patch(
            "devops_cli.commands.release.DocGenerator.check_docs",
            return_value=(True, []),
        ),
        patch("devops_cli.commands.release.run_subprocess") as mock_sub,
    ):
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["uv", "run", "devops", "ci", "run"],
            returncode=0,
            stdout="All checks passed!",
            stderr="",
        )
        result = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--allow-dirty"])
    assert result.exit_code == 0


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
        assert '"draft": true' in result.output.lower()
        assert "release/v0.1.8" in result.output
    finally:
        set_dry_run(False)


def test_release_pr_no_draft_override(sample_project_dir: Path) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        result = runner.invoke(
            app,
            [
                "pr",
                "--version",
                "0.1.8",
                "--no-draft",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert result.exit_code == 0
        assert '"draft": false' in result.output.lower()
    finally:
        set_dry_run(False)


def test_release_prepare_pr_draft_default(sample_project_dir: Path) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        result = runner.invoke(
            app,
            ["prepare", "0.1.8", "--create-pr", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert '"draft": true' in result.output.lower()
    finally:
        set_dry_run(False)


def test_release_pr_command(sample_project_dir: Path) -> None:
    def mock_gh_dispatch(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if "issue" in cmd:
            return subprocess.CompletedProcess(
                args=[CONST_GH_CLI, "issue", "list"],
                returncode=0,
                stdout='[{"number": 99, "title": "feat(core): core feature"}]',
                stderr="",
            )
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=[CONST_GH_CLI, "pr", "create"],
                returncode=0,
                stdout="https://github.com/your-org/devops-cli/pull/42\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with (
        patch("devops_cli.commands.release.run_subprocess") as mock_sub,
        patch("devops_cli.commands.release.run_gh", side_effect=mock_gh_dispatch) as mock_gh,
    ):
        mock_sub.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = runner.invoke(
            app,
            ["pr", "--version", "0.1.8", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert "Created Release Pull Request" in result.output
        assert "pull/42" in result.output
        assert mock_gh.called
        create_calls = [
            c[0][0] for c in mock_gh.call_args_list if "pr" in c[0][0] and "create" in c[0][0]
        ]
        assert len(create_calls) == 1
        create_args = create_calls[0]
        body_idx = create_args.index("--body") + 1
        assert "- #99" in create_args[body_idx]
        # Only the git calls that reach origin get the person's environment (#1124).
        git_calls = [(c.args[0][1], c.kwargs) for c in mock_sub.call_args_list]
        person_env_calls = [
            subcommand
            for subcommand, kwargs in git_calls
            if (kwargs.get("isolate_env"), kwargs.get("env"))
            == (False, CONST_GIT_NO_TERMINAL_PROMPT_ENV)
        ]
        isolate_flags = [kwargs.get("isolate_env", True) for _, kwargs in git_calls]
        assert (person_env_calls, isolate_flags.count(False)) == (["fetch", "push"], 2)


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
            patch(
                "devops_cli.commands.release.DocGenerator.check_docs",
                return_value=(True, []),
            ),
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
        patch(
            "devops_cli.commands.release.DocGenerator.check_docs",
            return_value=(True, []),
        ),
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


def test_release_tag_push_and_errors(
    sample_project_dir: Path,
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    git: Callable[..., None],
) -> None:
    """Verify devops release tag push and error branches; a pushed tag closes its Release.

    The Release closes in the tagged repository, which is not the checkout the tests run in.
    """
    git(sample_project_dir, "init", "--quiet")
    git(
        sample_project_dir,
        "remote",
        "add",
        "origin",
        "https://github.com/example/tagged.git",
    )
    roadmap_store.create_release("v0.1.7")
    # Dry run
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res_tag_dry = runner.invoke(
            app,
            ["tag", "--version", "0.1.7", "--push", "--root", str(sample_project_dir)],
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

    # A refused push exits 1 with git's reason, credentials masked, and closes no Release.
    # The remote's text is shown as written: a stray Rich closing tag in it raises nothing.
    leaked_token = "ghp_" + "b2" * 18

    def refuse_the_push(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        refused = "push" in cmd
        reason = f"remote: refused [/bold] for {leaked_token}" if refused else ""
        return subprocess.CompletedProcess(
            args=cmd, returncode=int(refused), stdout="", stderr=reason
        )

    with patch("devops_cli.commands.release.run_subprocess", side_effect=refuse_the_push):
        res_refused = runner.invoke(
            app,
            ["tag", "--version", "0.1.7", "--push", "--root", str(sample_project_dir)],
        )
    refused_output = " ".join(res_refused.output.split())
    still_open = roadmap_store.release("0.1.7")
    assert (
        res_refused.exit_code,
        "Failed to push tag v0.1.7 to origin: remote: refused [/bold] for" in refused_output,
        leaked_token in refused_output,
        still_open.state if still_open else None,
        roadmap_store_repos,
    ) == (1, True, False, GitHubState.OPEN, [])

    # Push tags success
    mock_ok = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
    with patch("devops_cli.commands.release.run_subprocess", return_value=mock_ok):
        res_push = runner.invoke(
            app,
            ["tag", "--version", "0.1.7", "--push", "--root", str(sample_project_dir)],
        )
    closed = roadmap_store.release("0.1.7")
    assert (
        res_push.exit_code,
        "Closed release milestone for v0.1.7" in res_push.output,
        closed.state if closed else None,
        roadmap_store_repos,
    ) == (0, True, GitHubState.CLOSED, ["example/tagged"])


def test_release_pr_labels_and_draft(sample_project_dir: Path) -> None:
    """Verify devops release pr label validation, draft options, and fail-closed error handling."""

    def mock_subproc(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="https://github.com/org/repo/pull/1\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with (
        patch("devops_cli.commands.release.run_subprocess", side_effect=mock_subproc),
        patch("devops_cli.commands.release.run_gh", side_effect=mock_gh),
    ):
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
        assert (res_bad_lbl.exit_code, "Invalid label" in res_bad_lbl.output) == (
            1,
            True,
        )

        res_pr_ok = runner.invoke(
            app,
            [
                "pr",
                "--version",
                "0.1.8",
                "--labels",
                "release, automated",
                "--draft",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert (
            res_pr_ok.exit_code,
            "Created Release Pull Request" in res_pr_ok.output,
        ) == (0, True)

        # Release check command
        with patch("devops_cli.docs.generator.DocGenerator.check_docs", return_value=(True, [])):
            res_check = runner.invoke(
                app,
                [
                    "check",
                    "--skip-ci",
                    "--allow-dirty",
                    "--root",
                    str(sample_project_dir),
                ],
            )
            assert (
                res_check.exit_code,
                "release verification checks passed" in res_check.output.lower(),
            ) == (0, True)

    def mock_gh_label_fail(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="GraphQL: Could not resolve to a Label: release",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with (
        patch("devops_cli.commands.release.run_subprocess", side_effect=mock_subproc),
        patch("devops_cli.commands.release.run_gh", side_effect=mock_gh_label_fail) as mock_gh_fail,
    ):
        res_fail = runner.invoke(
            app,
            [
                "pr",
                "--version",
                "0.1.8",
                "--labels",
                "release",
                "--root",
                str(sample_project_dir),
            ],
        )
        create_calls = [c[0][0] for c in mock_gh_fail.call_args_list if "create" in c[0][0]]
        assert (
            res_fail.exit_code,
            len(create_calls),
            "could not resolve to a label" in res_fail.output.lower(),
        ) == (1, 1, True)


def test_release_pr_error_branches_and_breaking(sample_project_dir: Path) -> None:
    """Verify release pr branch failure, breaking flag, and gh create failure."""
    mock_gh_empty = subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")

    # 1. Branch checkout failure
    with (
        patch(
            "devops_cli.commands.release.run_subprocess",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="git checkout error"
            ),
        ),
        patch("devops_cli.commands.release.run_gh", return_value=mock_gh_empty),
    ):
        res_br_fail = runner.invoke(
            app, ["pr", "--version", "0.1.8", "--root", str(sample_project_dir)]
        )
        assert res_br_fail.exit_code == 1

    # 2. Breaking change PR
    def mock_breaking_gh(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="https://github.com/org/repo/pull/2\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with (
        patch(
            "devops_cli.commands.release.run_subprocess",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ),
        patch("devops_cli.commands.release.run_gh", side_effect=mock_breaking_gh),
    ):
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
    def mock_gh_fail(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="gh: authentication required"
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with (
        patch(
            "devops_cli.commands.release.run_subprocess",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ),
        patch("devops_cli.commands.release.run_gh", side_effect=mock_gh_fail) as gh_fail_mock,
    ):
        res_gh_fail = runner.invoke(
            app, ["pr", "--version", "0.1.8", "--root", str(sample_project_dir)]
        )
        create_calls = [c[0][0] for c in gh_fail_mock.call_args_list if "create" in c[0][0]]
        assert (
            res_gh_fail.exit_code,
            len(create_calls),
            "authentication required" in res_gh_fail.output
            or "failed" in res_gh_fail.output.lower(),
        ) == (1, 1, True)


def test_release_notes_tag_and_check_extended(
    sample_project_dir: Path, roadmap_store: InMemoryRoadmapStore
) -> None:
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
    called: list[tuple[list[str], dict[str, Any]]] = []

    def mock_tag_subproc(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        called.append((cmd, kwargs))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_subprocess", side_effect=mock_tag_subproc):
        res_tag_ok = runner.invoke(
            app,
            ["tag", "--version", "0.1.8", "--push", "--root", str(sample_project_dir)],
        )
        assert res_tag_ok.exit_code == 0
        assert any("tag" in c and "-a" in c and "v0.1.8" in c for c, _ in called)
        # The push names the release tag alone, in the person's environment (#1124).
        pushes = [
            (cmd, kwargs.get("isolate_env"), kwargs.get("env"))
            for cmd, kwargs in called
            if "push" in cmd
        ]
        isolate_flags = [kwargs.get("isolate_env", True) for _, kwargs in called]
        assert (pushes, isolate_flags.count(False)) == (
            [
                (
                    ["git", "push", "origin", "refs/tags/v0.1.8"],
                    False,
                    CONST_GIT_NO_TERMINAL_PROMPT_ENV,
                )
            ],
            1,
        )
        # No Release v0.1.8 exists, so the pushed tag only warns that it closed none.
        assert "Could not close milestone for v0.1.8: No Release '0.1.8'" in res_tag_ok.output

    # 4. release check version mismatch
    pyproject_file = sample_project_dir / "pyproject.toml"
    pyproject_file.write_text('[project]\nname = "test"\nversion = "0.9.0"\n', encoding="utf-8")

    res_mismatch = runner.invoke(app, ["check", "--root", str(sample_project_dir)])
    assert res_mismatch.exit_code == 1
    assert "Version mismatch" in res_mismatch.output


def test_release_check_changelog_version_mismatch(sample_project_dir: Path) -> None:
    """Verify release check fails when CHANGELOG.md version differs from pyproject.toml."""
    changelog = sample_project_dir / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [0.1.6] - 2026-08-10\n\n- Old feature\n", encoding="utf-8"
    )

    with (
        patch("devops_cli.commands.release._is_git_clean", return_value=True),
        patch(
            "devops_cli.commands.release.DocGenerator.check_docs",
            return_value=(True, []),
        ),
    ):
        result = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--skip-ci"])
        assert result.exit_code == 1
        assert "Version mismatch: CHANGELOG.md" in result.output
        assert "0.1.6" in result.output
        assert "0.1.7" in result.output


def test_release_check_changelog_missing(sample_project_dir: Path) -> None:
    """Verify release check fails when CHANGELOG.md does not exist."""
    changelog = sample_project_dir / "CHANGELOG.md"
    if changelog.exists():
        changelog.unlink()

    with (
        patch("devops_cli.commands.release._is_git_clean", return_value=True),
        patch(
            "devops_cli.commands.release.DocGenerator.check_docs",
            return_value=(True, []),
        ),
    ):
        result = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--skip-ci"])
        assert result.exit_code == 1
        assert "Version mismatch: CHANGELOG.md (missing)" in result.output


def test_release_notes_fallback_to_docs(sample_project_dir: Path) -> None:
    """Verify release notes extracts from docs/RELEASE_NOTES.md when absent in CHANGELOG.md."""
    # CHANGELOG only has 0.1.7
    docs_rel_notes = sample_project_dir / "docs" / "RELEASE_NOTES.md"
    docs_rel_notes.write_text(
        "# Release Notes\n\n## 🚀 Highlights of v0.1.8\n\n- Fallback Doc Feature\n- Security hardening\n\n## Highlights of v0.1.7\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["notes", "--version", "0.1.8", "--raw", "--root", str(sample_project_dir)]
    )
    assert result.exit_code == 0
    assert "Fallback Doc Feature" in result.output
    assert "Security hardening" in result.output


def test_release_notes_fallback_to_git_log(sample_project_dir: Path) -> None:
    """Verify release notes falls back to git commit log when absent in changelog and docs."""
    mock_git_log = subprocess.CompletedProcess(
        args=["git", "log"],
        returncode=0,
        stdout="* feat: commit log item 1 (abc1234)\n* fix: commit log item 2 (def5678)\n",
        stderr="",
    )

    with patch("devops_cli.commands.release.run_subprocess", return_value=mock_git_log):
        result = runner.invoke(
            app,
            ["notes", "--version", "0.1.9", "--raw", "--root", str(sample_project_dir)],
        )
        assert result.exit_code == 0
        assert "Changes in v0.1.9" in result.output
        assert "commit log item 1" in result.output
        assert "commit log item 2" in result.output


def test_release_check_fails_on_empty_changelog(sample_project_dir: Path) -> None:
    """Verify release check fails when CHANGELOG.md section has no content."""
    changelog_file = sample_project_dir / "CHANGELOG.md"
    changelog_file.write_text(
        "# Changelog\n\n## [0.1.7] - 2026-08-13\n\n## [0.1.6] - 2026-08-12\n\n### Added\n- Initial.\n",
        encoding="utf-8",
    )
    with pytest.raises(typer.Exit):
        _verify_release_versions(sample_project_dir)

    result = runner.invoke(app, ["check", "--root", str(sample_project_dir), "--skip-ci"])
    assert result.exit_code != 0
    assert "entry for v0.1.7 is empty" in result.output


def test_release_notes_squash_commit_parsing(sample_project_dir: Path) -> None:
    """Verify squash commits with embedded bullets are extracted and categorized."""
    squash_body = (
        "feat(release): v0.1.9 (#100)\n\n"
        "* feat(security): cosign image signing (#101)\n"
        "* fix(k8s): elevate memory thresholds (#102)\n"
        "* docs: update user guide (#103)\n"
    )
    mock_git_log = subprocess.CompletedProcess(
        args=["git", "log"],
        returncode=0,
        stdout=squash_body,
        stderr="",
    )

    with patch("devops_cli.commands.release.run_subprocess", return_value=mock_git_log):
        notes = _extract_git_commit_notes(sample_project_dir, "0.1.9")
        assert notes is not None
        assert "### Added" in notes
        assert "cosign image signing" in notes
        assert "### Fixed & Hardened" in notes
        assert "elevate memory thresholds" in notes
        assert "### Changed & Improved" in notes
        assert "update user guide" in notes


def test_release_changelog_command(sample_project_dir: Path) -> None:
    """Verify devops release changelog command outputs and updates properly."""
    mock_git_log = subprocess.CompletedProcess(
        args=["git", "log"],
        returncode=0,
        stdout="* feat(auth): add oidc provider\n* fix(cli): handle timeout error\n",
        stderr="",
    )

    with patch("devops_cli.commands.release.run_subprocess", return_value=mock_git_log):
        # 1. Test raw output
        result = runner.invoke(
            app,
            [
                "changelog",
                "--version",
                "0.1.8",
                "--raw",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert result.exit_code == 0
        assert "add oidc provider" in result.output
        assert "handle timeout error" in result.output

        # 2. Test dry-run
        from devops_cli.dry_run import set_dry_run

        set_dry_run(True)
        try:
            dry_res = runner.invoke(
                app,
                ["changelog", "--version", "0.1.8", "--root", str(sample_project_dir)],
            )
            assert dry_res.exit_code == 0
            assert "compile_release_changelog" in dry_res.output
        finally:
            set_dry_run(False)

        # 3. Test --update
        update_res = runner.invoke(
            app,
            [
                "changelog",
                "--version",
                "0.1.8",
                "--update",
                "--root",
                str(sample_project_dir),
            ],
        )
        assert update_res.exit_code == 0
        changelog_content = (sample_project_dir / "CHANGELOG.md").read_text(encoding="utf-8")
        assert "## [0.1.8]" in changelog_content
        assert "add oidc provider" in changelog_content


def test_build_release_pr_body_draft_mode(sample_project_dir: Path) -> None:
    """Verify _build_release_pr_body in draft mode formats milestone items and has no checkbox."""
    import json

    from devops_cli.commands.release import _build_release_pr_body

    mock_issues = [
        {
            "number": 117,
            "title": "feat(ai): adaptive embedding batch sizing",
            "state": "OPEN",
        },
        {
            "number": 118,
            "title": "perf(ai): high-performance AST context packer",
            "state": "OPEN",
        },
    ]
    mock_gh_res = subprocess.CompletedProcess(
        args=[CONST_GH_CLI], returncode=0, stdout=json.dumps(mock_issues), stderr=""
    )

    with patch("devops_cli.commands.release.run_gh", return_value=mock_gh_res):
        body = _build_release_pr_body(
            repo_root=sample_project_dir,
            target_ver="0.2.19",
            base="main",
            branch_name="release/v0.2.19",
            draft=True,
            pr_title="feat(release): v0.2.19",
        )
        assert "## feat(release): v0.2.19" in body
        assert "Release `v0.2.19` tracking PR under GitHub pull request merge controls." in body
        assert "### Target Milestone Deliverables" in body
        assert "- #117" in body
        assert "- #118" in body
        assert "- **#117**" not in body
        assert _CHECKBOX_LINE.search(body) is None


def test_build_release_pr_body_ready_mode(sample_project_dir: Path) -> None:
    """Verify _build_release_pr_body in ready mode formats included deliverables and no checkbox.

    Its seven quality boxes were ticked on every ready release PR without reading anything;
    the PR's own checks are what GitHub shows.
    """
    from devops_cli.commands.release import _build_release_pr_body

    with patch(
        "devops_cli.commands.release.run_gh",
        return_value=subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=""),
    ):
        mock_log = subprocess.CompletedProcess(
            args=["git", "log"],
            returncode=0,
            stdout="* feat(security): cosign container signing (#213)\n",
            stderr="",
        )
        with patch("devops_cli.commands.release.run_subprocess", return_value=mock_log):
            body = _build_release_pr_body(
                repo_root=sample_project_dir,
                target_ver="0.2.19",
                base="main",
                branch_name="release/v0.2.19",
                draft=False,
                pr_title="feat(release): v0.2.19",
            )
            assert (
                "### Included Deliverables" in body,
                "feat(security): cosign container signing (#213)" in body,
                _CHECKBOX_LINE.search(body),
            ) == (True, True, None)


def test_resolve_clean_release_notes_stale_duplicate_fallback(
    sample_project_dir: Path,
) -> None:
    """Verify _resolve_clean_release_notes discards notes duplicated from the previous release."""
    from devops_cli.commands.release import _resolve_clean_release_notes

    changelog_path = sample_project_dir / "CHANGELOG.md"
    duplicate_content = (
        "## [0.2.19] - 2026-09-16\n\n"
        "### Added\n- Duplicate item from previous release.\n\n"
        "## [0.2.18] - 2026-09-16\n\n"
        "### Added\n- Duplicate item from previous release.\n\n"
    )
    changelog_path.write_text(duplicate_content, encoding="utf-8")

    mock_git_log = subprocess.CompletedProcess(
        args=["git", "log"],
        returncode=0,
        stdout="* feat(auth): add new oauth provider for 0.2.19\n",
        stderr="",
    )
    with patch("devops_cli.commands.release.run_subprocess", return_value=mock_git_log):
        notes = _resolve_clean_release_notes(
            repo_root=sample_project_dir,
            target_ver="0.2.19",
            base="main",
            branch_name="release/v0.2.19",
        )
        assert "Duplicate item from previous release" not in notes
        assert "add new oauth provider for 0.2.19" in notes


def test_query_gh_milestone_issues_all_states_and_standalone_prs(
    sample_project_dir: Path,
) -> None:
    """Verify _query_gh_milestone_issues queries with --state all and includes standalone PRs."""
    from devops_cli.commands.release import (
        _build_release_pr_command,
        _query_gh_milestone_issues,
    )

    def mock_run_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        import sys

        sys.stderr.write(f"MOCK_RUN_GH: {cmd}\n")
        if "issue" in cmd and "list" in cmd:
            assert ("--state" in cmd, "--milestone" in cmd) == (True, True)
            state_idx = cmd.index("--state")
            assert cmd[state_idx + 1] == "all"
            issues_json = json.dumps(
                [
                    {"number": 296, "title": "Epic: v0.2.21"},
                    {"number": 272, "title": "feat(ai): inspectional scanner"},
                    {"number": 280, "title": "fix(reliability): exception handling"},
                ]
            )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=issues_json, stderr=""
            )
        if "pr" in cmd and "list" in cmd:
            prs_json = json.dumps(
                [
                    {"number": 281, "title": "fix(reliability): harden (#280)"},
                    {"number": 292, "title": "feat(ai): routing services"},
                ]
            )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=prs_json, stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with (
        patch("devops_cli.github.rate_limiter.run_gh", side_effect=mock_run_gh),
        patch("devops_cli.commands.release.run_gh", side_effect=mock_run_gh),
    ):
        deliverables = _query_gh_milestone_issues(sample_project_dir, "v0.2.21")
        assert deliverables == ["- #272", "- #280", "- #292", "- #296"]

    # Verify _build_release_pr_command includes --milestone
    pr_cmd = _build_release_pr_command(
        pr_title="feat(release): v0.2.21",
        pr_body="body",
        base="main",
        branch_name="release/v0.2.21",
        draft=False,
        labels="release",
        milestone="v0.2.21",
    )
    assert ("--milestone" in pr_cmd, pr_cmd[pr_cmd.index("--milestone") + 1]) == (
        True,
        "v0.2.21",
    )


# =============================================================================
# Changelog compilation
# =============================================================================


def test_a_squash_merge_and_its_original_subject_are_one_entry() -> None:
    """A squash merge appends its pull request number; the body often keeps the original.

    Comparing whole lines missed the pair, so the same change was listed twice -- once as
    "... port-forwarding (#369)" and once bare.
    """
    from devops_cli.commands.release import _extract_raw_commit_lines

    log = (
        "feat(k8s): address cluster services without localhost port-forwarding (#369)\n"
        "feat(k8s): address cluster services without localhost port-forwarding\n"
    )
    assert _extract_raw_commit_lines(log) == [
        "feat(k8s): address cluster services without localhost port-forwarding (#369)"
    ]


def test_the_entry_keeps_the_pull_request_reference() -> None:
    """The reference is how a reader gets from the changelog to the change."""
    from devops_cli.commands.release import _extract_raw_commit_lines

    log = "fix(ci): drop the invalid --depth=0 (#355)\nfix(ci): drop the invalid --depth=0\n"
    assert "(#355)" in _extract_raw_commit_lines(log)[0]


def test_commit_body_prose_is_not_a_changelog_entry() -> None:
    """The log is read as full bodies, so every paragraph of a commit message arrives too.

    Those were filed under "Other Changes", and whole explanatory paragraphs reached a
    release description as bullet points.
    """
    from devops_cli.commands.release import _extract_raw_commit_lines

    log = (
        "fix(tui): correct the Docker, telemetry and Valkey panels (#368)\n"
        "Docker: the panel listed only running containers, so it disagreed with the CLI.\n"
        "Telemetry: the panel read the in-process metric registry, which is empty.\n"
        "Fixed:\n"
    )
    assert _extract_raw_commit_lines(log) == [
        "fix(tui): correct the Docker, telemetry and Valkey panels (#368)"
    ]


def test_a_colon_does_not_make_a_line_a_commit_subject() -> None:
    """`word:` matches ordinary prose, which is how "kubeconfig: selecting one that does
    not exist" became an entry. The type has to be one the project uses."""
    from devops_cli.commands.release import _is_conventional_subject

    assert [
        _is_conventional_subject(line)
        for line in (
            "feat(k8s): address cluster services",
            "fix: a thing",
            "kubeconfig: selecting one that does not exist breaks kubectl",
            'http://localhost:6333" while Qdrant was running healthily',
        )
    ] == [True, True, False, False]


def test_a_repository_without_conventional_commits_still_gets_entries() -> None:
    """Filtering on a convention the target does not follow would produce nothing at all."""
    from devops_cli.commands.release import _extract_raw_commit_lines

    log = "Added a retry around the upload\nRemoved the unused helper\n"
    assert len(_extract_raw_commit_lines(log)) == 2


def test_release_commits_are_excluded() -> None:
    """A release commit records the release; it is not one of its changes."""
    from devops_cli.commands.release import _extract_raw_commit_lines

    log = "feat(release): v0.2.22 (#335)\nfix(ci): a real change (#400)\n"
    assert _extract_raw_commit_lines(log) == ["fix(ci): a real change (#400)"]


def test_update_fills_a_section_that_already_has_an_entry(tmp_path: Path) -> None:
    """Population ran only when the section was empty.

    A section holding one entry kept one entry and had only its date refreshed, so
    `--update` reported success while the release stayed unwritten: v0.2.22 carried a
    single line against fifty-two commits.
    """
    from devops_cli.commands.release import _build_changelog_section

    with patch(
        "devops_cli.commands.release._extract_git_commit_notes",
        return_value="### Changes in v1.0.0\n\n### Added\n- feat(a): one (#1)\n- feat(b): two (#2)\n",
    ):
        section = _build_changelog_section(
            tmp_path,
            "1.0.0",
            "2026-09-22",
            existing_notes="### Added\n- feat(c): kept (#3)\n",
        )
    assert [marker in section for marker in ("kept (#3)", "one (#1)", "two (#2)")] == [
        True,
        True,
        True,
    ]


def test_an_entry_already_written_is_not_repeated(tmp_path: Path) -> None:
    """Re-running must not grow the section, or the command is unusable more than once."""
    from devops_cli.commands.release import _build_changelog_section

    with patch(
        "devops_cli.commands.release._extract_git_commit_notes",
        return_value="### Changes in v1.0.0\n\n### Added\n- feat(a): one (#1)\n",
    ):
        section = _build_changelog_section(
            tmp_path,
            "1.0.0",
            "2026-09-22",
            existing_notes="### Added\n- feat(a): one (#1)\n",
        )
    assert section.count("feat(a): one") == 1


def test_a_hand_written_entry_survives_recompilation(tmp_path: Path) -> None:
    """The file wins over the compiler, so an edited description is not reverted."""
    from devops_cli.commands.release import _merge_changelog_entries

    merged = _merge_changelog_entries(
        ["feat(a): a carefully worded description (#1)"],
        ["feat(a): a carefully worded description"],
    )
    assert merged == ["feat(a): a carefully worded description (#1)"]


def test_an_empty_section_is_still_populated(tmp_path: Path) -> None:
    """The case that did work must keep working."""
    from devops_cli.commands.release import _build_changelog_section

    with patch(
        "devops_cli.commands.release._extract_git_commit_notes",
        return_value="### Changes in v1.0.0\n\n### Added\n- feat(a): one (#1)\n",
    ):
        section = _build_changelog_section(tmp_path, "1.0.0", "2026-09-22", existing_notes=None)
    assert "feat(a): one (#1)" in section


def test_release_targets_the_nested_worktree_it_is_given(
    nested_worktree: tuple[Path, Path],
) -> None:
    """Verify `--root <nested worktree>` releases that worktree rather than the checkout around
    it, and the checkout still resolves to itself (#582)."""
    main, nested = nested_worktree

    roots = (_get_project_root(nested), _get_project_root(main))

    assert roots == (nested.resolve(), main.resolve())


# =============================================================================
# The cut collects changelog.d/ fragments (#933)
# =============================================================================

_UNRELEASED_CHANGELOG = (
    "# Changelog\n\n"
    "## [Unreleased]\n\n"
    "## [0.1.7] - 2026-08-13\n\n"
    "### Added\n- Native DevContainer Lifecycle.\n"
)
# Three fragments whose categories overlap, each written out of Keep a Changelog order.
_THREE_FRAGMENTS = {
    "100.md": "### Changed\n- **Hundred Changed** (#100).\n\n### Added\n- **Hundred Added** (#100).\n",
    "12.md": (
        "### Fixed\n- **Twelve Fixed**:\n  - detail (#12).\n\n"
        "### Added\n- **Twelve Added**:\n  - detail (#12).\n"
    ),
    "3.md": "### Security\n- **Three Security** (#3).\n\n### Fixed\n- **Three Fixed** (#3).\n",
}
_COLLECTED_CHANGELOG = (
    "# Changelog\n\n"
    "## [Unreleased]\n\n"
    "## [0.1.8] - <date>\n\n"
    "### Added\n- **Twelve Added**:\n  - detail (#12).\n- **Hundred Added** (#100).\n\n"
    "### Changed\n- **Hundred Changed** (#100).\n\n"
    "### Fixed\n- **Three Fixed** (#3).\n- **Twelve Fixed**:\n  - detail (#12).\n\n"
    "### Security\n- **Three Security** (#3).\n\n"
    "## [0.1.7] - 2026-08-13\n\n"
    "### Added\n- Native DevContainer Lifecycle.\n"
)


def _with_fragments(project: Path, fragments: dict[str, str]) -> Path:
    """Open `[Unreleased]` in the project's changelog and write `changelog.d/` with a README."""
    (project / "CHANGELOG.md").write_text(_UNRELEASED_CHANGELOG, encoding="utf-8")
    fragments_dir = project / "changelog.d"
    fragments_dir.mkdir()
    (fragments_dir / "README.md").write_text("Fragments.\n", encoding="utf-8")
    for name, text in fragments.items():
        (fragments_dir / name).write_text(text, encoding="utf-8")
    return project


def _changelog_with_date_masked(project: Path) -> str:
    """The changelog with the cut's own date, which is today's, replaced by `<date>`."""
    text = (project / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.sub(r"(## \[0\.1\.8\] - )\d{4}-\d{2}-\d{2}", r"\1<date>", text)


def _left_in_changelog_d(project: Path) -> list[str]:
    return sorted(path.name for path in (project / "changelog.d").iterdir())


def test_the_cut_merges_three_fragments_into_one_section_and_deletes_them(
    sample_project_dir: Path,
) -> None:
    """Categories in Keep a Changelog order, fragments in issue order within each, text intact.

    Every PR into a release branch wrote at the top of `[Unreleased]`, so each merge made
    every other open PR conflict: #928 and #932 each conflicted twice in one hour (#933).
    """
    project = _with_fragments(sample_project_dir, _THREE_FRAGMENTS)
    with patch("devops_cli.commands.release.DocGenerator.write_all_docs"):
        result = runner.invoke(app, ["prepare", "0.1.8", "--root", str(project)])
    assert (
        result.exit_code,
        _changelog_with_date_masked(project),
        _left_in_changelog_d(project),
        _get_pyproject_version(project),
    ) == (0, _COLLECTED_CHANGELOG, ["README.md"], "0.1.8"), result.output


def test_release_changelog_update_collects_the_fragments_too(
    sample_project_dir: Path,
) -> None:
    """`devops release changelog --update` writes the version's section the same way."""
    project = _with_fragments(sample_project_dir, _THREE_FRAGMENTS)
    with patch("devops_cli.commands.release._extract_git_commit_notes", return_value=None):
        result = runner.invoke(
            app, ["changelog", "--version", "0.1.8", "--update", "--root", str(project)]
        )
    assert (
        result.exit_code,
        _changelog_with_date_masked(project),
        _left_in_changelog_d(project),
    ) == (0, _COLLECTED_CHANGELOG, ["README.md"]), result.output


@pytest.mark.parametrize(
    ("name", "text", "reason"),
    [
        (
            "7.md",
            "### Improvements\n- x (#7).\n",
            "changelog.d/7.md:1 '### Improvements' is not",
        ),
        (
            "7.md",
            "A note first.\n\n### Added\n- x (#7).\n",
            "changelog.d/7.md:1 is outside a",
        ),
        (
            "notes.md",
            "### Added\n- x.\n",
            "changelog.d/notes.md is not a changelog fragment",
        ),
    ],
    ids=["unknown-category", "text-outside-a-category", "misnamed-file"],
)
def test_a_bad_fragment_stops_the_cut_before_any_write(
    sample_project_dir: Path, name: str, text: str, reason: str
) -> None:
    """The fragments are checked before the version bump, so a refusal leaves every file as it was."""
    project = _with_fragments(sample_project_dir, {**_THREE_FRAGMENTS, name: text})
    with patch("devops_cli.commands.release.DocGenerator.write_all_docs") as docs:
        result = runner.invoke(app, ["prepare", "0.1.8", "--root", str(project)])
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        reason in output,
        (project / "CHANGELOG.md").read_text(encoding="utf-8"),
        _left_in_changelog_d(project),
        (_get_pyproject_version(project), _get_init_version(project), docs.call_count),
    ) == (
        1,
        True,
        _UNRELEASED_CHANGELOG,
        sorted([*_THREE_FRAGMENTS, name, "README.md"]),
        ("0.1.7", "0.1.7", 0),
    ), result.output


@pytest.mark.parametrize("command", [["prepare", "0.1.8"], ["changelog", "-v", "0.1.8", "-u"]])
def test_a_dry_run_cut_names_the_fragments_and_writes_nothing(
    sample_project_dir: Path, command: list[str]
) -> None:
    """A dry run reads the fragments, so it refuses what the cut would, and deletes none."""
    from devops_cli.dry_run import set_dry_run

    project = _with_fragments(sample_project_dir, _THREE_FRAGMENTS)
    set_dry_run(True)
    try:
        with patch("devops_cli.commands.release._extract_git_commit_notes", return_value=None):
            result = runner.invoke(app, [*command, "--root", str(project)])
    finally:
        set_dry_run(False)
    assert (
        result.exit_code,
        all(f"changelog.d/{name}" in result.output for name in ("3.md", "12.md", "100.md")),
        (project / "CHANGELOG.md").read_text(encoding="utf-8"),
        _left_in_changelog_d(project),
        _get_pyproject_version(project),
    ) == (
        0,
        True,
        _UNRELEASED_CHANGELOG,
        sorted([*_THREE_FRAGMENTS, "README.md"]),
        "0.1.7",
    )


@pytest.mark.parametrize(
    "unreleased",
    ["## [Unreleased]\n\n### Fixed\n- By hand.\n\n", "## [Unreleased]\n\n"],
    ids=["unreleased-with-entries", "unreleased-empty"],
)
@pytest.mark.parametrize("readme_only", [True, False], ids=["readme-only", "no-directory"])
def test_without_fragments_the_section_is_built_as_the_current_code_builds_it(
    tmp_path: Path, unreleased: str, readme_only: bool
) -> None:
    """No fragment means no change: `[Unreleased]` is renamed, or filled from the commits."""
    from devops_cli.commands.release import (
        _plan_fragment_collection,
        _write_version_changelog,
    )

    changelog = "# Changelog\n\n" + unreleased + "## [0.1.7] - 2026-08-13\n\n### Added\n- Old.\n"
    project, before = tmp_path / "project", tmp_path / "before"
    for root in (project, before):
        root.mkdir()
        (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    if readme_only:
        (project / "changelog.d").mkdir()
        (project / "changelog.d" / "README.md").write_text("Fragments.\n", encoding="utf-8")
    commits = "### Changes in v0.1.8\n\n### Added\n- feat(a): one (#1)\n"
    with patch("devops_cli.commands.release._extract_git_commit_notes", return_value=commits):
        plan = _plan_fragment_collection(project, "0.1.8", "2026-10-02")
        written = _write_version_changelog(project, "0.1.8", "2026-10-02", plan)
        _update_changelog_header(before, "0.1.8", "2026-10-02")
    assert (plan, written, (project / "CHANGELOG.md").read_text(encoding="utf-8")) == (
        None,
        True,
        (before / "CHANGELOG.md").read_text(encoding="utf-8"),
    )


def test_a_release_commit_stages_changelog_d_only_where_it_exists(
    tmp_path: Path,
) -> None:
    """The cut deletes the fragments, so the release commit records the deletions.

    Naming a path that does not exist would fail the whole `git add`.
    """
    from devops_cli.commands.release import _release_paths

    without = _release_paths(tmp_path)
    (tmp_path / "changelog.d").mkdir()
    assert (without[-1], _release_paths(tmp_path)[-1]) == ("docs/", "changelog.d/")


# =============================================================================
# Release notes fit GitHub's body limits (#1097)
# =============================================================================

_SECTION_HEADING = "## [0.2.25] - 2026-10-03"
_SECTION_URL = "https://github.com/dan-petty/devops-cli/blob/v0.2.25/CHANGELOG.md#0225---2026-10-03"
_REPO_CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def _with_section(project: Path, body: str) -> Path:
    """Put `body` in the project's changelog as the `[0.2.25]` section, above `[0.1.7]`."""
    changelog = project / "CHANGELOG.md"
    older = changelog.read_text(encoding="utf-8").split("## [0.1.7]", 1)[1]
    changelog.write_text(f"# Changelog\n\n{_SECTION_HEADING}\n\n{body}\n\n## [0.1.7]{older}")
    return project


@pytest.fixture
def repository_named(monkeypatch: pytest.MonkeyPatch) -> str:
    """The repository GitHub Actions names; the project directory has no git origin."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "dan-petty/devops-cli")
    return "dan-petty/devops-cli"


def _no_github() -> Any:
    """Every gh and git call fails, as offline: no milestone deliverables, no branch log."""
    failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    return (
        patch("devops_cli.commands.release.run_gh", return_value=failed),
        patch("devops_cli.commands.release.run_subprocess", return_value=failed),
    )


def _pr_body(project: Path, version: str = "0.2.25") -> str:
    from devops_cli.commands.release import _build_release_pr_body

    gh, git = _no_github()
    with gh, git:
        return _build_release_pr_body(
            repo_root=project,
            target_ver=version,
            base="main",
            branch_name=f"release/v{version}",
            draft=False,
            pr_title=f"feat(release): v{version}",
        )


def test_release_notes_that_fit_are_printed_unchanged(sample_project_dir: Path) -> None:
    """Below the limit the Release body is the changelog section, character for character."""
    body = "### Added\n- **A Feature**:\n  - its detail (#1).\n\n### Fixed\n- **A Fix** (#2)."
    _with_section(sample_project_dir, body)
    result = runner.invoke(
        app,
        ["notes", "--version", "0.2.25", "--raw", "--root", str(sample_project_dir)],
    )
    assert (result.exit_code, result.output) == (0, body + "\n")


def test_a_200000_character_section_prints_under_the_release_limit_with_its_link(
    sample_project_dir: Path, repository_named: str
) -> None:
    """Every category and title, no sub-bullet, and the section's link at its tag, last."""
    _with_section(sample_project_dir, synthetic_release_section())
    result = runner.invoke(
        app,
        ["notes", "--version", "0.2.25", "--raw", "--root", str(sample_project_dir)],
    )
    titles = [synthetic_entry_title(number) for number in range(1, SYNTHETIC_ENTRY_COUNT + 1)]
    assert result.exit_code == 0
    assert len(result.output) < CONST_GITHUB_RELEASE_BODY_MAX_CHARS
    assert [title for title in titles if title not in result.output] == []
    assert [c for c in SYNTHETIC_CATEGORIES if f"### {c}\n" not in result.output] == []
    assert synthetic_entry_detail(1, 1) not in result.output
    assert result.output.endswith(f"[`CHANGELOG.md` at v0.2.25]({_SECTION_URL}).\n")


def test_without_a_known_repository_the_pointer_names_the_file_and_tag(
    sample_project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No origin and no GITHUB_REPOSITORY: no URL can be built, so none is guessed."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    _with_section(sample_project_dir, synthetic_release_section())
    result = runner.invoke(
        app,
        ["notes", "--version", "0.2.25", "--raw", "--root", str(sample_project_dir)],
    )
    assert result.output.endswith("The full notes are in `CHANGELOG.md` at v0.2.25.\n")


def test_the_changelog_fallback_prints_notes_that_fit_unchanged_and_fits_the_rest(
    sample_project_dir: Path, repository_named: str
) -> None:
    """`release.yml` falls back to `release changelog --raw`; its output obeys the same rule."""
    small = "* feat(auth): add oidc provider\n* fix(cli): handle timeout error\n"
    large = "".join(f"* feat(x): change number {n} of a long release (#{n})\n" for n in range(3000))
    outputs = []
    for log in (small, large):
        git_log = subprocess.CompletedProcess(args=[], returncode=0, stdout=log, stderr="")
        with patch("devops_cli.commands.release.run_subprocess", return_value=git_log):
            compiled = _extract_git_commit_notes(sample_project_dir, "0.1.8")
            result = runner.invoke(
                app,
                [
                    "changelog",
                    "--version",
                    "0.1.8",
                    "--raw",
                    "--root",
                    str(sample_project_dir),
                ],
            )
        outputs.append((compiled, result.output))
    (small_notes, small_output), (large_notes, large_output) = outputs
    assert small_output == f"{small_notes}\n"
    assert len(large_notes) > CONST_GITHUB_RELEASE_BODY_MAX_CHARS
    assert len(large_output) <= CONST_GITHUB_RELEASE_BODY_MAX_CHARS
    assert "Entries left out to fit: " in large_output
    assert large_output.endswith(
        "[`CHANGELOG.md` at v0.1.8](https://github.com/dan-petty/devops-cli/blob/v0.1.8/CHANGELOG.md).\n"
    )


def test_the_release_pr_body_fits_its_limit_with_every_title(
    sample_project_dir: Path, repository_named: str
) -> None:
    """The PR limit is about half the Release one; the 210 titles still fit under it."""
    body = _pr_body(_with_section(sample_project_dir, synthetic_release_section()))
    titles = [synthetic_entry_title(number) for number in range(1, SYNTHETIC_ENTRY_COUNT + 1)]
    assert len(body) <= CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS
    assert [title for title in titles if title not in body] == []
    assert f"({_SECTION_URL})." in body


def test_the_release_pr_body_counts_its_other_sections_against_the_limit(
    sample_project_dir: Path, repository_named: str
) -> None:
    """Notes that fit the limit alone are compacted when the deliverables push the body over."""
    from devops_cli.commands.release import _build_release_pr_body

    entry = "- **An Entry**:\n  - " + "d" * 300
    notes = "### Added\n" + "\n".join([entry] * 200)
    assert len(notes) < CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS
    issues = [
        {"number": n, "title": f"feat: deliverable {n}", "state": "CLOSED"} for n in range(400)
    ]
    listed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=json.dumps(issues), stderr=""
    )
    _with_section(sample_project_dir, notes)
    with (
        patch("devops_cli.commands.release.run_gh", return_value=listed),
        patch(
            "devops_cli.commands.release._extract_branch_release_notes",
            return_value=None,
        ),
    ):
        body = _build_release_pr_body(
            repo_root=sample_project_dir,
            target_ver="0.2.25",
            base="main",
            branch_name="release/v0.2.25",
            draft=False,
            pr_title="feat(release): v0.2.25",
        )
    assert len(body) <= CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS
    assert ("- #399" in body, "d" * 300 in body, f"({_SECTION_URL})." in body) == (
        True,
        False,
        True,
    )


def test_every_section_of_this_repositorys_changelog_fits_both_limits(
    sample_project_dir: Path, repository_named: str
) -> None:
    """Including v0.2.25's 196,525 characters once the cut is in this branch's CHANGELOG.md."""
    from devops_cli.commands.release import _release_body_notes

    changelog = _REPO_CHANGELOG.read_text(encoding="utf-8")
    (sample_project_dir / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    sizes = {
        version: (
            len(_release_body_notes(sample_project_dir, version) or ""),
            len(_pr_body(sample_project_dir, version)),
        )
        for version in versions
    }
    assert len(sizes) > 30
    assert {
        version: size
        for version, size in sizes.items()
        if size[0] >= CONST_GITHUB_RELEASE_BODY_MAX_CHARS
        or size[1] > CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS
    } == {}


# =============================================================================
# Fail-closed Release Cut Orchestration Tests (#982)
# =============================================================================


@pytest.fixture
def git_release_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Create a bare remote repository with origin/main and origin/release/v0.2.26, and a clone."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        check=True,
        capture_output=True,
    )

    clone = tmp_path / "clone"
    clone.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=clone, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "ci@example.com"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "CI Bot"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(origin)],
        cwd=clone,
        check=True,
        capture_output=True,
    )

    src = clone / "src" / "devops_cli"
    src.mkdir(parents=True)
    (clone / "pyproject.toml").write_text(
        '[project]\nname = "devops-cli"\nversion = "0.2.25"\nrequires-python = ">=3.14"\n',
        encoding="utf-8",
    )
    (src / "__init__.py").write_text('__version__ = "0.2.25"\n', encoding="utf-8")
    (clone / "CHANGELOG.md").write_text(
        "## [0.2.25] - 2026-09-01\n- Initial release.\n", encoding="utf-8"
    )
    (clone / "README.md").write_text("# devops-cli\n", encoding="utf-8")
    (clone / "docs").mkdir(parents=True, exist_ok=True)
    (clone / "docs" / "index.md").write_text("# Docs\n", encoding="utf-8")
    (clone / "uv.lock").write_text(
        'version = 1\nrevision = 3\nrequires-python = ">=3.14"\n\n[[package]]\nname = "devops-cli"\nversion = "0.2.25"\nsource = { virtual = "." }\n',
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=clone, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: initial commit"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=clone,
        check=True,
        capture_output=True,
    )

    subprocess.run(
        ["git", "checkout", "-b", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    (clone / "README.md").write_text("# devops-cli v0.2.26\n", encoding="utf-8")
    subprocess.run(
        ["git", "commit", "-am", "chore: release preparation"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )

    subprocess.run(
        ["git", "checkout", "-b", "feature/my-work"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    return origin, clone


def test_release_prepare_dirty_tree_rejection(
    git_release_repo: tuple[Path, Path],
) -> None:
    """devops release prepare --create-pr rejects dirty trees without creating branches."""
    _, clone = git_release_repo
    (clone / "dirty.txt").write_text("uncommitted change\n", encoding="utf-8")
    status_before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=clone, capture_output=True, text=True
    ).stdout

    res = runner.invoke(app, ["prepare", "0.2.26", "--create-pr", "--root", str(clone)])
    status_after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=clone, capture_output=True, text=True
    ).stdout
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=clone,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert (
        res.exit_code,
        "uncommitted changes" in res.output.lower(),
        status_after == status_before,
        current_branch,
    ) == (1, True, True, "feature/my-work")


def test_release_cut_pushes_from_remote_release_tip_and_leaves_main_untouched(
    git_release_repo: tuple[Path, Path],
) -> None:
    """Release cut pushes release/v0.2.26 derived from remote tip without moving main."""
    origin, clone = git_release_repo
    main_before = subprocess.run(
        ["git", "rev-parse", "refs/heads/main"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()
    rel_before = subprocess.run(
        ["git", "rev-parse", "refs/heads/release/v0.2.26"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()

    gh_calls: list[list[str]] = []

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        gh_calls.append(list(cmd))
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="https://github.com/example/repo/pull/10\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(
            app,
            [
                "prepare",
                "0.2.26",
                "--create-pr",
                "--no-sync-docs",
                "--root",
                str(clone),
            ],
        )

    main_after = subprocess.run(
        ["git", "rev-parse", "refs/heads/main"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()
    rel_after = subprocess.run(
        ["git", "rev-parse", "refs/heads/release/v0.2.26"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()
    parent_commit = subprocess.run(
        ["git", "rev-parse", "refs/heads/release/v0.2.26^"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()
    diff_files = (
        subprocess.run(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "refs/heads/release/v0.2.26",
            ],
            cwd=origin,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .splitlines()
    )

    create_calls = [c for c in gh_calls if "pr" in c and "create" in c]
    has_merge_or_review = any("merge" in c or "review" in c for c in gh_calls)

    assert (
        res.exit_code,
        main_after == main_before,
        rel_after != rel_before,
        parent_commit == rel_before,
        sorted(diff_files),
        len(create_calls),
        has_merge_or_review,
    ) == (
        0,
        True,
        True,
        True,
        ["pyproject.toml", "src/devops_cli/__init__.py", "uv.lock"],
        1,
        False,
    )

    pr_cmd = create_calls[0]
    assert (
        pr_cmd[pr_cmd.index("--base") + 1],
        pr_cmd[pr_cmd.index("--head") + 1],
        pr_cmd[pr_cmd.index("--title") + 1],
        pr_cmd[pr_cmd.index("--label") + 1],
        pr_cmd[pr_cmd.index("--milestone") + 1],
        "--draft" in pr_cmd,
    ) == (
        "main",
        "release/v0.2.26",
        "feat(release): v0.2.26",
        "release",
        "v0.2.26",
        True,
    )


def test_uv_lock_check_offline_passes_after_bump(
    git_release_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    """uv lock --check --offline passes on the bumped pyproject.toml and uv.lock."""
    import shutil

    if not shutil.which("uv"):
        pytest.skip("uv binary not available on PATH")

    _, clone = git_release_repo

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="https://github.com/example/repo/pull/11\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(
            app,
            [
                "prepare",
                "0.2.26",
                "--create-pr",
                "--no-sync-docs",
                "--root",
                str(clone),
            ],
        )
    assert res.exit_code == 0

    stage = tmp_path / "uv_check_stage"
    stage.mkdir()
    shutil.copy(clone / "pyproject.toml", stage / "pyproject.toml")
    shutil.copy(clone / "uv.lock", stage / "uv.lock")
    cache_dir = tmp_path / "empty_uv_cache"
    cache_dir.mkdir()
    # The stage has no virtual environment, so name the interpreter: offline, uv cannot
    # download one, and a CI runner has no Python 3.14 on its search path.
    env = {**os.environ, "UV_CACHE_DIR": str(cache_dir), "UV_PYTHON": sys.executable}
    check_proc = subprocess.run(
        ["uv", "lock", "--check", "--offline"],
        cwd=stage,
        env=env,
        capture_output=True,
        text=True,
    )
    assert check_proc.returncode == 0


def test_release_cut_fails_when_origin_release_branch_absent(
    git_release_repo: tuple[Path, Path],
) -> None:
    """Missing origin/release/v<version> exits non-zero naming branch without creating refs."""
    _, clone = git_release_repo
    res = runner.invoke(app, ["prepare", "0.9.99", "--create-pr", "--root", str(clone)])
    status_porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=clone, capture_output=True, text=True
    ).stdout.strip()
    cut_branch = subprocess.run(
        ["git", "branch", "--list", "release/v0.9.99"],
        cwd=clone,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert (
        res.exit_code,
        "origin/release/v0.9.99" in res.output,
        status_porcelain,
        cut_branch,
    ) == (1, True, "", "")


def test_release_cut_stops_when_the_release_branch_fetch_fails(
    git_release_repo: tuple[Path, Path],
) -> None:
    """A failed fetch stops the cut with git's reason, so a stale tracking ref is never cut (#1124).

    The remote deleted `release/v0.2.26`, but the clone still holds `origin/release/v0.2.26`.
    """
    origin, clone = git_release_repo
    for repo in (origin, clone):
        subprocess.run(
            ["git", "branch", "-D", "release/v0.2.26"], cwd=repo, check=True, capture_output=True
        )
    gh_calls: list[list[str]] = []

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        gh_calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(app, ["pr", "--version", "0.2.26", "--root", str(clone)])

    output = " ".join(res.output.split())
    branches = subprocess.run(
        ["git", "branch", "--list", "release/v0.2.26"],
        cwd=clone,
        capture_output=True,
        text=True,
    ).stdout.strip()
    head = subprocess.run(
        ["git", "branch", "--show-current"], cwd=clone, capture_output=True, text=True
    ).stdout.strip()
    assert (
        res.exit_code,
        "Failed to fetch origin/release/v0.2.26" in output,
        "couldn't find remote ref release/v0.2.26" in output,
        branches,
        head,
        gh_calls,
    ) == (1, True, True, "", "feature/my-work", [])


def test_release_cut_stops_when_the_fetch_writes_no_tracking_ref(
    git_release_repo: tuple[Path, Path],
) -> None:
    """A clone that fetches only `main` gets no `origin/release/v<version>`, and the cut stops."""
    _, clone = git_release_repo
    for git_args in (
        ["config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main"],
        ["update-ref", "-d", "refs/remotes/origin/release/v0.2.26"],
    ):
        subprocess.run(["git", *git_args], cwd=clone, check=True, capture_output=True)
    gh_calls: list[list[str]] = []

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        gh_calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(app, ["pr", "--version", "0.2.26", "--root", str(clone)])

    assert (
        res.exit_code,
        "Remote release branch 'origin/release/v0.2.26' does not exist." in res.output,
        gh_calls,
    ) == (1, True, [])


def test_release_cut_rebuilds_on_new_remote_tip(
    git_release_repo: tuple[Path, Path],
) -> None:
    """Subsequent cut run rebuilds cut branch from updated remote tip with force-with-lease."""
    origin, clone = git_release_repo

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="https://github.com/example/repo/pull/12\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res1 = runner.invoke(
            app,
            [
                "prepare",
                "0.2.26",
                "--create-pr",
                "--no-sync-docs",
                "--root",
                str(clone),
            ],
        )
    assert res1.exit_code == 0

    # Advance release/v0.2.26 on origin
    subprocess.run(
        ["git", "checkout", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    (clone / "new_feature.txt").write_text("added commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "new_feature.txt"], cwd=clone, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: advance release"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    new_tip = subprocess.run(
        ["git", "rev-parse", "refs/heads/release/v0.2.26"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()

    subprocess.run(
        ["git", "checkout", "feature/my-work"],
        cwd=clone,
        check=True,
        capture_output=True,
    )

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res2 = runner.invoke(
            app,
            [
                "prepare",
                "0.2.26",
                "--create-pr",
                "--no-sync-docs",
                "--root",
                str(clone),
            ],
        )

    current_tip = subprocess.run(
        ["git", "rev-parse", "refs/heads/release/v0.2.26"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert (res2.exit_code, current_tip == new_tip) == (0, True)


def test_release_cut_without_uv_lock(git_release_repo: tuple[Path, Path]) -> None:
    """Repositories without uv.lock neither create nor stage uv.lock during release cut."""
    origin, clone = git_release_repo
    subprocess.run(
        ["git", "checkout", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "rm", "uv.lock"], cwd=clone, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: delete uv.lock"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "feature/my-work"],
        cwd=clone,
        check=True,
        capture_output=True,
    )

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="https://github.com/example/repo/pull/13\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(
            app,
            [
                "prepare",
                "0.2.26",
                "--create-pr",
                "--no-sync-docs",
                "--root",
                str(clone),
            ],
        )

    diff_files = (
        subprocess.run(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "refs/heads/release/v0.2.26",
            ],
            cwd=origin,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .splitlines()
    )
    assert (res.exit_code, "uv.lock" in diff_files, (clone / "uv.lock").exists()) == (
        0,
        False,
        False,
    )


@pytest.mark.parametrize(
    ("command", "hook", "git_says"),
    [
        (
            ["prepare", "0.2.26", "--create-pr", "--no-sync-docs"],
            "pre-receive",
            "[remote rejected]",
        ),
        # `release pr` pushes the unchanged remote tip, so only the clone's own hook can refuse.
        (["pr", "--version", "0.2.26"], "pre-push", "failed to push some refs"),
    ],
    ids=["prepare-create-pr", "pr"],
)
def test_release_cut_rejected_push_stops_before_gh(
    git_release_repo: tuple[Path, Path], command: list[str], hook: str, git_says: str
) -> None:
    """A rejected push exits non-zero and opens no pull request.

    The error carries git's reason as written, brackets included, with any credential in it
    masked (#1124).
    """
    origin, clone = git_release_repo
    leaked_token = "ghp_" + "a1" * 18
    hook_file = {"pre-receive": origin / "hooks", "pre-push": clone / ".git" / "hooks"}[hook] / hook
    hook_file.parent.mkdir(exist_ok=True)
    hook_file.write_text(
        f"#!/bin/sh\necho 'rejected by {hook} hook for {leaked_token}' >&2\nexit 1\n",
        encoding="utf-8",
    )
    hook_file.chmod(0o755)

    gh_called = False

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal gh_called
        gh_called = True
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(app, [*command, "--root", str(clone)])

    output = " ".join(res.output.split())
    assert (
        res.exit_code,
        gh_called,
        "Failed to push release/v0.2.26 to origin" in output,
        f"rejected by {hook} hook" in output,
        git_says in output,
        leaked_token in output,
    ) == (1, False, True, True, True, False)


def _give_git_a_persons_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    """Set what a person's credential helper reads, as the devcontainer does, and return it.

    The helper lives in `GIT_CONFIG_*`, and VS Code's socket, the keyring's session bus and an
    SSH agent are what helpers reach. Both GitHub token variables are set too, as a person's
    shell may set them. `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` name an empty file, so no
    helper of the developer's own answers.
    """
    empty_config = tmp_path / "empty.gitconfig"
    empty_config.write_text("", encoding="utf-8")
    persons = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "credential.https://example.com.helper",
        "GIT_CONFIG_VALUE_0": "!fake-helper",
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={tmp_path / 'bus'}",
        "REMOTE_CONTAINERS_IPC": str(tmp_path / "vscode-ipc.sock"),
        "SSH_AUTH_SOCK": str(tmp_path / "ssh-agent.sock"),
    }
    ambient = {
        "GIT_CONFIG_GLOBAL": str(empty_config),
        "GIT_CONFIG_SYSTEM": str(empty_config),
        "GH_TOKEN": "ambient-token",
        "GITHUB_TOKEN": "other-token",
    }
    for name, value in {**persons, **ambient}.items():
        monkeypatch.setenv(name, value)
    return persons


def _record_what_pre_push_sees(clone: Path, record: Path, names: list[str]) -> None:
    """Make `clone`'s pre-push hook write the variables `names` and git's example.com helper.

    Only those variables are written, so the rest of the environment never reaches the disk.
    """
    hook = clone / ".git" / "hooks" / "pre-push"
    only_names = shlex.quote(f"^({'|'.join(names)})=")
    hook.write_text(
        "#!/bin/sh\n"
        f"env | grep -E {only_names} > {shlex.quote(str(record / 'env'))}\n"
        "git config --get-all credential.https://example.com.helper"
        f" > {shlex.quote(str(record / 'helper'))}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)


@pytest.mark.parametrize("has_github_login", [True, False], ids=["gh-login", "no-gh-login"])
def test_release_pr_pushes_in_the_persons_git_environment(
    git_release_repo: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    has_github_login: bool,
) -> None:
    """The push sees the person's credential helper and what it reaches, with no prompt (#1124).

    GitHub's token stays the session's (#767): the push gets it as GH_TOKEN and no other, and
    without a gh login it gets no token at all.
    """
    _, clone = git_release_repo
    persons = _give_git_a_persons_environment(tmp_path, monkeypatch)
    if not has_github_login:
        fail_the_github_lookup(monkeypatch)
    record = tmp_path / "pre-push"
    record.mkdir()
    shown = [*persons, "GIT_TERMINAL_PROMPT", "GH_TOKEN", "GITHUB_TOKEN"]
    _record_what_pre_push_sees(clone, record, shown)

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        created = "https://github.com/example/repo/pull/7\n" if "create" in cmd else "[]"
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=created, stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(app, ["pr", "--version", "0.2.26", "--root", str(clone)])

    env_lines = (record / "env").read_text(encoding="utf-8").splitlines()
    seen = dict(line.partition("=")[::2] for line in env_lines)
    assert (
        res.exit_code,
        (record / "helper").read_text(encoding="utf-8").strip(),
        {name: seen.get(name) for name in shown},
    ) == (
        0,
        "!fake-helper",
        {
            **persons,
            "GIT_TERMINAL_PROMPT": "0",
            "GH_TOKEN": PINNED_GITHUB_TOKEN if has_github_login else None,
            "GITHUB_TOKEN": None,
        },
    )


def test_release_pr_alone_pushes_remote_tip_and_resolves_tip_version(
    git_release_repo: tuple[Path, Path],
) -> None:
    """release pr alone pushes cut branch identical to remote tip and resolves tip version."""
    origin, clone = git_release_repo
    # Remote tip pyproject.toml has version 0.2.26
    subprocess.run(
        ["git", "checkout", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    (clone / "pyproject.toml").write_text(
        '[project]\nname = "devops-cli"\nversion = "0.2.26"\n', encoding="utf-8"
    )
    subprocess.run(
        ["git", "commit", "-am", "chore: bump version to 0.2.26 on release branch"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", "release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    rel_tip = subprocess.run(
        ["git", "rev-parse", "refs/heads/release/v0.2.26"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()

    # Switch back to clean feature branch where pyproject.toml has version 0.2.25
    subprocess.run(
        ["git", "checkout", "feature/my-work"],
        cwd=clone,
        check=True,
        capture_output=True,
    )

    gh_cmds: list[list[str]] = []

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        gh_cmds.append(list(cmd))
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="https://github.com/example/repo/pull/14\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(app, ["pr", "--version", "0.2.26", "--root", str(clone)])

    cut_commit = subprocess.run(
        ["git", "rev-parse", "refs/heads/release/v0.2.26"],
        cwd=origin,
        capture_output=True,
        text=True,
    ).stdout.strip()
    create_cmds = [c for c in gh_cmds if "pr" in c and "create" in c]
    pr_title = create_cmds[0][create_cmds[0].index("--title") + 1] if create_cmds else ""

    assert (res.exit_code, cut_commit == rel_tip, pr_title) == (
        0,
        True,
        "feat(release): v0.2.26",
    )

    # On dirty tree, release pr exits non-zero before writing git refs
    (clone / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    res_dirty = runner.invoke(app, ["pr", "--version", "0.2.26", "--root", str(clone)])
    assert res_dirty.exit_code == 1


def test_release_pr_help_has_no_push() -> None:
    """release pr --help displays no push option flag."""
    res = runner.invoke(app, ["pr", "--help"])
    assert (res.exit_code, "--push" in res.output, "--no-push" in res.output) == (
        0,
        False,
        False,
    )


def test_release_prepare_and_pr_dry_run_cut_branch(sample_project_dir: Path) -> None:
    """Dry-run executions output release/v<version>, base main, and chdir/gh safety."""
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res_prep = runner.invoke(
            app, ["prepare", "0.2.26", "--create-pr", "--root", str(sample_project_dir)]
        )
        res_pr = runner.invoke(
            app, ["pr", "--version", "0.2.26", "--root", str(sample_project_dir)]
        )
    finally:
        set_dry_run(False)

    assert (
        res_prep.exit_code,
        "release/v0.2.26" in res_prep.output,
        "main" in res_prep.output,
        "feat(release): v0.2.26" in res_prep.output,
        "changelog_fragments" in res_prep.output,
    ) == (0, True, True, True, True)

    assert (
        res_pr.exit_code,
        "release/v0.2.26" in res_pr.output,
        "main" in res_pr.output,
        "feat(release): v0.2.26" in res_pr.output,
        "changelog_fragments" in res_pr.output,
    ) == (0, True, True, True, True)


def test_release_cut_ruleset_refusal_raises_typed_error(
    git_release_repo: tuple[Path, Path],
) -> None:
    """A ruleset rejection (GH013) raises ReleasePushRefusedError diagnosing bypass (#1280)."""
    origin, clone = git_release_repo
    hook_file = origin / "hooks" / "pre-receive"
    hook_file.parent.mkdir(exist_ok=True)
    ruleset_msg = (
        "remote: error: GH013: Repository rule violations found for refs/heads/release/v0.2.26.\n"
        "remote: Review rule violations: https://github.com/example.com/dan-petty/devops-cli/rulesets/23059172\n"
        "To origin\n"
        " ! [remote rejected] release/v0.2.26 -> release/v0.2.26 (pre-receive hook declined)\n"
        "error: failed to push some refs to 'origin'\n"
    )
    hook_file.write_text(
        f"#!/bin/sh\ncat > /dev/null\nprintf '%s' {shlex.quote(ruleset_msg)} >&2\nexit 1\n",
        encoding="utf-8",
    )
    hook_file.chmod(0o755)

    from devops_cli.commands.release import cut_release

    gh_called = False

    def mock_gh(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal gh_called
        gh_called = True
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with (
        patch("devops_cli.commands.release.run_gh", side_effect=mock_gh),
        pytest.raises(ReleasePushRefusedError) as exc_info,
    ):
        cut_release(version="0.2.26", repo_root=clone, is_prepare=True)

    exc = exc_info.value
    assert (
        isinstance(exc, (ReleasePushError, GitOperationError, DevOpsCLIError)),
        gh_called,
        "GH013" in exc.message,
        "23059172" in exc.message,
        "Write" in exc.message,
    ) == (True, False, True, True, True)

    # CLI command invocation wraps and reports ruleset refusal
    with patch("devops_cli.commands.release.run_gh", side_effect=mock_gh):
        res = runner.invoke(app, ["prepare", "0.2.26", "--create-pr", "--root", str(clone)])
    assert (
        res.exit_code,
        gh_called,
        "GH013" in res.output,
        "23059172" in res.output,
        "Write" in res.output,
    ) == (1, False, True, True, True)


def test_release_cut_failure_modes_raise_typed_devops_cli_errors(
    git_release_repo: tuple[Path, Path],
) -> None:
    """Every failure mode in cut_release raises a typed DevOpsCLIError subclass (#1280)."""
    origin, clone = git_release_repo
    from devops_cli.commands.release import cut_release

    # 1. Dirty tree raises ReleaseWorkingTreeDirtyError
    dirty_file = clone / "uncommitted.txt"
    dirty_file.write_text("wip\n", encoding="utf-8")
    with pytest.raises(ReleaseWorkingTreeDirtyError) as dirty_exc:
        cut_release(version="0.2.26", repo_root=clone)
    dirty_file.unlink()

    # 2. Remote fetch failure raises ReleaseRemoteFetchError
    subprocess.run(
        ["git", "branch", "-D", "release/v0.2.26"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    with pytest.raises(ReleaseRemoteFetchError) as fetch_exc:
        cut_release(version="0.2.26", repo_root=clone)

    # Recreate remote release branch for next steps
    subprocess.run(
        ["git", "branch", "release/v0.2.26", "main"],
        cwd=origin,
        check=True,
        capture_output=True,
    )

    # 3. Missing tracking ref rev-parse failure raises ReleaseBranchMissingError
    subprocess.run(
        ["git", "config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", "-d", "refs/remotes/origin/release/v0.2.26"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    with pytest.raises(ReleaseBranchMissingError) as missing_exc:
        cut_release(version="0.2.26", repo_root=clone)

    # Restore fetch refspec and tracking ref
    subprocess.run(
        ["git", "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "fetch", "origin"], cwd=clone, check=True, capture_output=True)

    # 4. PR creation failure raises ReleasePRCreationError
    def mock_gh_fail(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pr" in cmd and "create" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="GraphQL error: duplicate PR"
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    with (
        patch("devops_cli.commands.release.run_gh", side_effect=mock_gh_fail),
        pytest.raises(ReleasePRCreationError) as pr_exc,
    ):
        cut_release(version="0.2.26", repo_root=clone)

    assert (
        isinstance(dirty_exc.value, GitOperationError),
        "uncommitted changes" in dirty_exc.value.message.lower(),
        isinstance(fetch_exc.value, GitOperationError),
        "Failed to fetch origin/release/v0.2.26" in fetch_exc.value.message,
        isinstance(missing_exc.value, GitOperationError),
        "does not exist" in missing_exc.value.message,
        isinstance(pr_exc.value, DevOpsCLIError),
        "duplicate PR" in pr_exc.value.message,
    ) == (True, True, True, True, True, True, True, True)
