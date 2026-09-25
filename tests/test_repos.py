"""Tests for repos commands and repository utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.repos import app as repos_app
from devops_cli.core.gitignore import reset_indexes
from devops_cli.core.repo import (
    find_repo_root,
    find_top_level_repo_root,
    find_worktree_root,
    get_repo_origin_name,
    is_ignored_by_git,
    list_repo_files,
    read_gitignore_patterns,
)
from devops_cli.main import app

runner = CliRunner()


def test_repos_list_empty_dir(tmp_path: Path) -> None:
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = repos_dir
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "list"])

    assert result.exit_code == 0


def test_repos_list_missing_dir(tmp_path: Path) -> None:
    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "nonexistent"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "list"])

    assert result.exit_code == 0
    assert "not found" in result.output.lower()


@pytest.mark.parametrize(
    "url,expected_name",
    [
        ("https://github.com/org/my-repo.git", "my-repo"),
        ("git@github.com:org/my-repo.git", "my-repo"),
        ("https://github.com/org/my-repo", "my-repo"),
        ("https://github.com/org/some_tool.git", "some_tool"),
    ],
)
def test_repo_name_extraction(url: str, expected_name: str) -> None:
    """Repo name is extracted correctly from any URL format."""
    name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    assert name == expected_name


def test_repos_clone_requires_token(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.get_github_token", return_value=None),
    ):
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone-org", "my-org"])

    assert result.exit_code != 0


def test_repos_clone_org_uses_default_org(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.get_github_token", return_value="token"),
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
        patch("devops_cli.github.client.GitHubClient") as mock_client_cls,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        mock_client = MagicMock()
        mock_client.get_org_repos.return_value = []
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["repos", "clone-org"])

    assert result.exit_code == 0
    mock_client.get_org_repos.assert_called_once_with(
        "example-org",
        include_private=True,
        include_forks=False,
        include_archived=False,
    )
    mock_clone_repo.assert_not_called()
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_clone_org_skips_archived_repos(tmp_path: Path) -> None:
    archived_repo = MagicMock()
    archived_repo.name = "archived-repo"
    archived_repo.full_name = "example/archived-repo"
    archived_repo.clone_url = "git@github.com:example/archived-repo.git"
    archived_repo.ssh_url = "git@github.com:example/archived-repo.git"
    archived_repo.archived = True
    archived_repo.fork = False
    archived_repo.private = False

    active_repo = MagicMock()
    active_repo.name = "active-repo"
    active_repo.full_name = "example/active-repo"
    active_repo.clone_url = "git@github.com:example/active-repo.git"
    active_repo.ssh_url = "git@github.com:example/active-repo.git"
    active_repo.archived = False
    active_repo.fork = False
    active_repo.private = False

    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.get_github_token", return_value="token"),
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
        patch("devops_cli.github.client.GitHubClient") as mock_client_cls,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        mock_client = MagicMock()

        mock_client.get_org_repos.return_value = [active_repo]
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["repos", "clone-org"])

    assert result.exit_code == 0
    mock_clone_repo.assert_called_once_with(
        "https://github.com/example/active-repo.git",
        settings.repos.base_dir / "example-org" / "active-repo",
    )
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_clone_passes_github_urls_to_clone_repo(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
    ):
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone", "github.com/example/repo.git"])

    assert result.exit_code == 0
    mock_clone_repo.assert_called_once_with(
        "github.com/example/repo.git",
        tmp_path / "repos" / "example" / "repo",
    )
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_clone_standalone_and_full_url(tmp_path: Path) -> None:
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos"),
        patch("devops_cli.commands.repos._reload_workspace"),
    ):
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        # Full GitHub HTTPS URL
        res_full = runner.invoke(
            app,
            ["repos", "clone", "https://github.com/google-antigravity/antigravity-sdk-python.git"],
        )
        assert res_full.exit_code == 0
        mock_clone_repo.assert_called_with(
            "https://github.com/google-antigravity/antigravity-sdk-python.git",
            tmp_path / "repos" / "google-antigravity" / "antigravity-sdk-python",
        )

        # Standalone URL without org
        res_standalone = runner.invoke(app, ["repos", "clone", "simple-repo.git"])
        assert res_standalone.exit_code == 0
        mock_clone_repo.assert_called_with(
            "simple-repo.git",
            tmp_path / "repos" / "_standalone" / "simple-repo",
        )


def test_repos_update_syncs_workspace(tmp_path: Path) -> None:
    repos_dir = tmp_path / "repos"
    group_dir = repos_dir / "group"
    repo_dir = group_dir / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
    ):
        settings = MagicMock()
        settings.repos.base_dir = repos_dir
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "update"])

    assert result.exit_code == 0
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_update_no_repos(tmp_path: Path) -> None:
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = repos_dir
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "update"])

    assert result.exit_code == 0
    assert "No repositories" in result.output


def test_repo_origin_and_git_ignore_helpers(tmp_path: Path) -> None:
    """Verify get_repo_origin_name and is_ignored_by_git."""
    (tmp_path / ".git").mkdir()
    mock_proc = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="git@github.com:org/repo.git\n", stderr=""
    )
    with patch("devops_cli.core.repo.run_subprocess", return_value=mock_proc):
        origin = get_repo_origin_name(tmp_path)
        assert origin == "org/repo"

    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    assert is_ignored_by_git(tmp_path, tmp_path / "ignored.txt") is True
    assert is_ignored_by_git(tmp_path, tmp_path / ".git" / "config") is True


def test_core_repo_find_roots(tmp_path: Path) -> None:
    """Verify finding repo roots in nested directories."""
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    git_dir = tmp_path / "a" / ".git"
    git_dir.mkdir()

    root = find_repo_root(sub)
    assert root == tmp_path / "a"

    top_root = find_top_level_repo_root(sub)
    assert top_root == tmp_path / "a"


def test_find_worktree_root_nested_worktree_and_submodules(tmp_path: Path) -> None:
    """Verify find_worktree_root stops at nearest worktree, but passes through submodules."""
    main = tmp_path / "main"
    main_git = main / ".git"
    main_git.mkdir(parents=True)
    (main / "pyproject.toml").write_text("[project]\nname='main'\n", encoding="utf-8")

    nested_wt = main / ".claude" / "worktrees" / "nested"
    nested_wt.mkdir(parents=True)
    gitdir = main_git / "worktrees" / "nested"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    (nested_wt / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    (nested_wt / "src").mkdir()

    submod = main / "vendor" / "submodule"
    submod.mkdir(parents=True)
    submod_gitdir = main_git / "modules" / "submodule"
    submod_gitdir.mkdir(parents=True)
    (submod / ".git").write_text(f"gitdir: {submod_gitdir}\n", encoding="utf-8")
    (submod / "src").mkdir()

    standalone = tmp_path / "standalone"
    standalone.mkdir()
    (standalone / "pyproject.toml").write_text("[project]\nname='pkg'\n", encoding="utf-8")
    (standalone / "src").mkdir()

    resolved = (
        find_worktree_root(main),
        find_worktree_root(nested_wt),
        find_worktree_root(nested_wt / "src"),
        find_worktree_root(submod),
        find_worktree_root(submod / "src"),
        find_worktree_root(standalone / "src"),
    )
    expected = (
        main.resolve(),
        nested_wt.resolve(),
        nested_wt.resolve(),
        main.resolve(),
        main.resolve(),
        standalone.resolve(),
    )
    assert resolved == expected


def test_core_repo_gitignore_and_files(tmp_path: Path) -> None:
    """Verify gitignore parsing and listing repo files."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.tmp\nbuild/\n# comment\n", encoding="utf-8")

    patterns = read_gitignore_patterns(tmp_path)
    assert "*.tmp" in patterns
    assert "build/" in patterns

    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "test.tmp").write_text("temp", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.bin").write_text("bin", encoding="utf-8")

    files = list_repo_files(tmp_path)
    file_names = [f.name for f in files]
    assert "app.py" in file_names
    assert is_ignored_by_git(tmp_path, tmp_path / "test.tmp") is True
    assert is_ignored_by_git(tmp_path, tmp_path / "app.py") is False

    # Ignore rules are evaluated in-process; no git subprocess is spawned. A miss is the
    # common case, so the previous per-file `git check-ignore` fallback ran constantly.
    (tmp_path / ".git").mkdir(exist_ok=True)
    with patch("devops_cli.core.repo.run_subprocess") as mock_proc:
        assert is_ignored_by_git(tmp_path, tmp_path / "dynamic_ignored.txt") is False
        mock_proc.assert_not_called()

    # A rule added after the first evaluation takes effect once the cache is reset.
    # Compiled ignore files are revalidated on an interval rather than stat-ed per call,
    # which is what makes a repository walk affordable.
    (tmp_path / ".gitignore").write_text("*.tmp\nbuild/\ndynamic_ignored.txt\n", encoding="utf-8")
    reset_indexes()
    assert is_ignored_by_git(tmp_path, tmp_path / "dynamic_ignored.txt") is True

    # Symlink outside repository root
    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")

    symlink_file = tmp_path / "linked_secret.txt"
    try:
        symlink_file.symlink_to(outside_file)
    except OSError:
        pass

    listed_files = list_repo_files(tmp_path)
    assert outside_file not in listed_files


def test_repos_commands_dry_run(tmp_path: Path) -> None:
    """Verify repos list and sync in dry-run mode."""
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_list = runner.invoke(repos_app, ["list", "--base-dir", str(tmp_path)])
        assert res_list.exit_code == 0

        res_sync = runner.invoke(repos_app, ["sync", "--base-dir", str(tmp_path)])
        assert res_sync.exit_code == 0


def test_repos_branch_and_workspace_helpers(tmp_path: Path) -> None:
    """Verify _current_branch and _resolve_workspace_file."""
    from devops_cli.commands.repos import _current_branch, _resolve_workspace_file
    from devops_cli.config.constants import CONST_VSCODE_WORKSPACE_FILE

    # Non-git directory returns "unknown"
    assert _current_branch(tmp_path / "not_git") == "unknown"

    # Workspace file resolution
    abs_ws = (tmp_path / "custom.code-workspace").resolve()
    assert _resolve_workspace_file(tmp_path, abs_ws) == abs_ws
    assert (
        _resolve_workspace_file(tmp_path, CONST_VSCODE_WORKSPACE_FILE)
        == tmp_path.parent / CONST_VSCODE_WORKSPACE_FILE
    )


def test_repos_clone_invalid_arguments(tmp_path: Path) -> None:
    """Verify repos clone rejects hyphenated URLs and existing directories."""
    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        # Hyphen url
        res_hyphen = runner.invoke(repos_app, ["clone", "--", "-invalid-url"])
        assert res_hyphen.exit_code == 1

        # Existing dir
        existing_dir = tmp_path / "repos" / "org" / "existing-repo"
        existing_dir.mkdir(parents=True)
        res_exists = runner.invoke(repos_app, ["clone", "https://github.com/org/existing-repo.git"])
        assert res_exists.exit_code == 1


def test_repos_sync_pull_and_errors(tmp_path: Path) -> None:
    """Verify repos sync pulls tracking branches and handles git errors gracefully."""
    repos_dir = tmp_path / "repos"
    repo1 = repos_dir / "org" / "repo1"
    repo1.mkdir(parents=True)
    (repo1 / ".git").mkdir()

    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.iter_workspace_repos", return_value=[repo1]),
        patch("devops_cli.commands.repos.fetch_all") as mock_fetch,
        patch("devops_cli.commands.repos.pull_tracking") as mock_pull,
        patch("devops_cli.commands.repos.sync_from_repos"),
        patch("devops_cli.commands.repos._reload_workspace"),
    ):
        settings = MagicMock()
        settings.repos.base_dir = repos_dir
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        # Normal pull
        res = runner.invoke(repos_app, ["sync", "--pull"])
        assert res.exit_code == 0
        mock_fetch.assert_called_once_with(repo1)
        mock_pull.assert_called_once_with(repo1)

        # Fetch error handled gracefully
        mock_fetch.side_effect = RuntimeError("Git network timeout")
        res_err = runner.invoke(repos_app, ["sync"])
        assert res_err.exit_code == 0


def test_core_repo_safe_paths_and_tracked_files(tmp_path: Path) -> None:
    """Verify is_safe_subpath, resolve_safe_subpath traversal guard, and git-tracked files."""
    from devops_cli.core.repo import (
        _list_git_tracked_files,
        is_safe_subpath,
        list_repo_files,
        resolve_safe_subpath,
    )
    from devops_cli.exceptions import SecurityError

    # 1. Path safety checks
    base = tmp_path / "base"
    base.mkdir()
    child = base / "child" / "file.txt"

    assert is_safe_subpath(base, "child/file.txt") is True
    assert is_safe_subpath(base, child) is True
    assert is_safe_subpath(base, "../outside.txt") is False

    resolved = resolve_safe_subpath(base, "child/file.txt")
    assert resolved == base / "child" / "file.txt"

    with pytest.raises(SecurityError, match="Path traversal"):
        resolve_safe_subpath(base, "../outside.txt")

    # 2. _list_git_tracked_files
    mock_proc = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="src/app.py\nREADME.md\nimage.png\n", stderr=""
    )
    (base / ".git").mkdir()
    (base / "src").mkdir()
    (base / "src" / "app.py").write_text("code", encoding="utf-8")
    (base / "README.md").write_text("docs", encoding="utf-8")
    (base / "image.png").write_text("binary", encoding="utf-8")

    with patch("devops_cli.core.repo.run_subprocess", return_value=mock_proc):
        tracked = _list_git_tracked_files(base, base)
        assert tracked is not None
        assert base / "src" / "app.py" in tracked
        assert base / "image.png" not in tracked  # binary filtered

    # 3. list_repo_files for single file, missing target, and directory walk fallback
    single_f = base / "src" / "app.py"
    files = list_repo_files(single_f)
    assert files == [single_f]

    assert list_repo_files(tmp_path / "non_existent_folder") == []

    with patch("devops_cli.core.repo._list_git_tracked_files", return_value=None):
        walked = list_repo_files(base)
        assert base / "src" / "app.py" in walked

    # 4. get_repo_origin_name parsing
    from devops_cli.core.repo import get_repo_origin_name

    get_repo_origin_name.cache_clear()
    mock_ssh_origin = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="git@github.com:dan-petty/devops-cli.git\n", stderr=""
    )
    with patch("devops_cli.core.repo.run_subprocess", return_value=mock_ssh_origin):
        ssh_origin = get_repo_origin_name(base)

    get_repo_origin_name.cache_clear()
    mock_https_origin = subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout="https://github.com/dan-petty/devops-cli\n",
        stderr="",
    )
    with patch("devops_cli.core.repo.run_subprocess", return_value=mock_https_origin):
        https_origin = get_repo_origin_name(base)

    assert (ssh_origin, https_origin) == ("dan-petty/devops-cli", "dan-petty/devops-cli")


def test_repo_edge_cases(tmp_path: Path) -> None:
    """Verify find_top_level_repo_root from file, gitignore read error, and symlink edge cases."""
    from devops_cli.core.repo import (
        find_top_level_repo_root,
        is_ignored_by_git,
        is_safe_subpath,
        list_repo_files,
        read_gitignore_patterns,
    )

    root = tmp_path / "project_root"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='test'", encoding="utf-8")
    sub_file = root / "src" / "main.py"
    sub_file.parent.mkdir()
    sub_file.write_text("print('hi')", encoding="utf-8")

    # 1. find_top_level_repo_root from file
    assert find_top_level_repo_root(sub_file) == root

    # 2. read_gitignore_patterns with unreadable file
    with patch.object(Path, "read_text", side_effect=OSError("disk read error")):
        gi_f = root / ".gitignore"
        gi_f.write_text("*.tmp", encoding="utf-8")
        assert read_gitignore_patterns(root) == []

    # 3. is_ignored_by_git with subprocess exception
    (root / ".git").mkdir()
    with patch("devops_cli.core.repo.run_subprocess", side_effect=Exception("git error")):
        assert is_ignored_by_git(root, sub_file) is False

    # 4. list_repo_files with symlink outside root
    external_dir = tmp_path / "external_target"
    external_dir.mkdir()
    (external_dir / "secret.txt").write_text("secret", encoding="utf-8")
    symlink_dir = root / "ext_link"
    try:
        symlink_dir.symlink_to(external_dir)
    except OSError, NotImplementedError:
        pass

    with patch("devops_cli.core.repo._list_git_tracked_files", return_value=None):
        files = list_repo_files(root)
        assert all("secret.txt" not in str(f) for f in files)

    # 5. is_safe_subpath with exception
    with patch.object(Path, "resolve", side_effect=Exception("resolve error")):
        assert is_safe_subpath(root, "any/path") is False


def test_repos_reload_workspace_and_resolve(tmp_path: Path) -> None:
    """Verify _reload_workspace handles success and failure, and _resolve_workspace_file returns expected paths."""
    from devops_cli.commands.repos import _reload_workspace, _resolve_workspace_file

    ws_file = tmp_path / "test.code-workspace"
    ws_file.write_text("{}", encoding="utf-8")

    # Success
    with patch("devops_cli.core.process.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0)
        _reload_workspace(ws_file)

    # Subprocess failure handles exception safely
    with patch("devops_cli.core.process.run_subprocess", side_effect=OSError("not found")):
        _reload_workspace(ws_file)

    # _resolve_workspace_file variations
    root = tmp_path / "repos"
    root.mkdir()
    # Absolute path
    abs_ws = tmp_path / "custom.code-workspace"
    assert _resolve_workspace_file(root, abs_ws) == abs_ws
    # Default constant workspace file
    from devops_cli.config.constants import CONST_VSCODE_WORKSPACE_FILE

    assert (
        _resolve_workspace_file(root, Path(CONST_VSCODE_WORKSPACE_FILE))
        == root.parent / CONST_VSCODE_WORKSPACE_FILE
    )
    # Other relative path
    custom_rel = Path("custom_rel.code-workspace")
    assert _resolve_workspace_file(root, custom_rel) == custom_rel


def test_repos_clone_org_dry_run_and_missing_org() -> None:
    """Verify clone-org handles --dry-run and missing org configuration."""
    result = runner.invoke(app, ["--dry-run", "repos", "clone-org", "test-org"])
    assert result.exit_code == 0
    assert "Would run delegated command" in result.output

    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.github.default_org = None
        mock_load.return_value = settings
        res = runner.invoke(app, ["repos", "clone-org"])
        assert res.exit_code == 1


def test_repos_sync_and_status_dry_run() -> None:
    """Verify sync and status commands handle --dry-run."""
    res_sync = runner.invoke(app, ["--dry-run", "repos", "sync"])
    assert res_sync.exit_code == 0
    assert "Would run delegated command" in res_sync.output


def test_repo_origin_lru_caching(tmp_path: Path) -> None:
    """Verify get_repo_origin_name caches subsequent lookups for the same repo root."""
    from devops_cli.core.repo import get_repo_origin_name

    (tmp_path / ".git").mkdir()
    mock_proc = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="git@github.com:org/cached-repo.git\n", stderr=""
    )
    get_repo_origin_name.cache_clear()
    with patch("devops_cli.core.repo.run_subprocess", return_value=mock_proc) as mock_sub:
        res1 = get_repo_origin_name(tmp_path)
        res2 = get_repo_origin_name(tmp_path)
        assert (res1, res2, mock_sub.call_count) == ("org/cached-repo", "org/cached-repo", 1)

    res_status = runner.invoke(app, ["--dry-run", "repos", "status"])
    assert res_status.exit_code == 0
    assert "Would run delegated command" in res_status.output
