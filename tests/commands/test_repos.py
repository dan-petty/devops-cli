"""Tests for repos commands and repository utilities."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple
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
    is_stale_linked_worktree,
    list_repo_files,
    main_worktree_root,
    read_gitignore_patterns,
)
from devops_cli.main import app
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

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


def test_repos_clone_requires_a_gh_login(tmp_path: Path, no_github_identity: None) -> None:
    """Without a token from `gh auth token`, clone-org stops and says to run `gh auth login`."""
    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone-org", "my-org"])

    assert (result.exit_code != 0, "gh auth login" in result.output) == (True, True)


_ORG_REPOS = "/orgs/example-org/repos?type=all&per_page=100"


def _recorded_repositories() -> list[dict[str, Any]]:
    """The repositories GitHub listed for octocat, as recorded: Hello-World, linguist (a fork)
    and Spoon-Knife."""
    recorded = json.loads(
        (FIXTURES / "github" / "hello_world_repositories.json").read_text(encoding="utf-8")
    )
    return list(recorded["repositories"])


def test_repos_clone_org_uses_default_org(
    tmp_path: Path, github_api: GitHubApiFake, pin_github_session: str
) -> None:
    github_api.route("GET", _ORG_REPOS, github_json([]))
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone-org"])

    assert result.exit_code == 0
    assert (github_api.requested, {r.headers["authorization"] for r in github_api.sent}) == (
        [f"GET https://api.github.com{_ORG_REPOS}"],
        {f"token {pin_github_session}"},
    )
    mock_clone_repo.assert_not_called()
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_clone_org_skips_archived_repos(tmp_path: Path, github_api: GitHubApiFake) -> None:
    active_repo, _fork, archived_repo = _recorded_repositories()
    archived_repo = {**archived_repo, "archived": True}
    github_api.route("GET", _ORG_REPOS, github_json([archived_repo, active_repo]))

    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos") as mock_sync,
        patch("devops_cli.commands.repos._reload_workspace") as mock_reload,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone-org"])

    assert result.exit_code == 0
    mock_clone_repo.assert_called_once_with(
        "https://github.com/octocat/Hello-World.git",
        settings.repos.base_dir / "example-org" / "Hello-World",
    )
    mock_sync.assert_called_once_with(settings.repos.base_dir.resolve(), settings.workspace.file)
    mock_reload.assert_called_once_with(settings.workspace.file)


def test_repos_clone_org_skips_path_traversal_repo(
    tmp_path: Path, github_api: GitHubApiFake
) -> None:
    """Verify clone-org skips repositories with path traversal attempts."""
    bad_repo = {**_recorded_repositories()[0], "name": "../escape"}
    github_api.route("GET", _ORG_REPOS, github_json([bad_repo]))

    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
        patch("devops_cli.commands.repos.sync_from_repos"),
        patch("devops_cli.commands.repos._reload_workspace"),
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone-org"])

    assert (result.exit_code, mock_clone_repo.called) == (0, False)


def test_repos_clone_org_rejects_path_traversal_org(
    tmp_path: Path, github_api: GitHubApiFake
) -> None:
    """Verify clone-org aborts when organization name attempts path traversal."""
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
    ):
        settings = MagicMock()
        settings.github.default_org = "example-org"
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone-org", "../escaped-org"])

    assert (result.exit_code, mock_clone_repo.called, github_api.requested) == (1, False, [])


def test_repos_clone_org_names_the_missing_organization(
    tmp_path: Path, cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    """A name that is no organization and not the session's login is reported by GitHub's own
    error, without a traceback, and nothing is created for it."""
    github_api.route("GET", "/user", github_json({"login": "somebody-else"}))
    destination = tmp_path / "repos"

    result = cli("repos", "clone-org", "no-such-org", "--base-dir", str(destination))

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "HTTP 404" in result.output
    assert not destination.exists()


def test_repos_clone_rejects_path_traversal_destination(tmp_path: Path) -> None:
    """Verify clone aborts when URL components attempt path traversal."""
    with (
        patch("devops_cli.commands.repos.load_settings") as mock_load,
        patch("devops_cli.commands.repos.clone_repo") as mock_clone_repo,
    ):
        settings = MagicMock()
        settings.repos.base_dir = tmp_path / "repos"
        settings.workspace.file = tmp_path / ".code-workspace"
        mock_load.return_value = settings

        result = runner.invoke(app, ["repos", "clone", "git@example.com:../../escaped/repo.git"])

    assert (result.exit_code, mock_clone_repo.called) == (1, False)


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
        patch("devops_cli.commands.repos.fetch_all"),
        patch("devops_cli.commands.repos.pull_tracking"),
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


def test_repo_origin_and_git_ignore_helpers(tmp_path: Path, git_fake: GitFake) -> None:
    """Verify get_repo_origin_name and is_ignored_by_git."""
    (tmp_path / ".git").mkdir()
    git_fake.answer(
        ["git", "remote", "get-url", "origin"],
        ProcessAnswer(stdout="git@github.com:org/repo.git\n"),
    )
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
    """Verify find_worktree_root stops at nearest worktree, but passes through submodules,
    and a directory with no repository markers resolves to itself."""
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
    plain = tmp_path / "plain"
    plain.mkdir()

    resolved = (
        find_worktree_root(main),
        find_worktree_root(nested_wt),
        find_worktree_root(nested_wt / "src"),
        find_worktree_root(submod),
        find_worktree_root(submod / "src"),
        find_worktree_root(standalone / "src"),
        find_worktree_root(plain),
    )
    expected = (
        main.resolve(),
        nested_wt.resolve(),
        nested_wt.resolve(),
        main.resolve(),
        main.resolve(),
        standalone.resolve(),
        plain.resolve(),
    )
    assert resolved == expected


# #582: Claude Code puts linked worktrees under `<checkout>/.claude/worktrees/`. A linked
# worktree checks itself, while the main checkout, its submodules, repositories cloned under
# `repos/` and the worktrees of such a clone resolve to the workspace, and a stale worktree
# still checks itself. The data directory always stays the workspace's.


class Workspace(NamedTuple):
    """A checkout with every kind of nested repository a workspace can hold."""

    main: Path
    nested: Path
    outside: Path
    submodule: Path
    clone: Path


def _make_worktree(
    repo_root: Path, wt_path: Path, branch: str = "wt", *, relative: bool = False
) -> None:
    wt_path.mkdir(parents=True, exist_ok=True)
    git_base = repo_root if (repo_root / "config").is_file() else repo_root / ".git"
    gitdir = git_base / "worktrees" / branch
    gitdir.mkdir(parents=True, exist_ok=True)
    if relative:
        rel_to_common = os.path.relpath(git_base, gitdir)
        (gitdir / "commondir").write_text(f"{rel_to_common}\n", encoding="utf-8")
        (gitdir / "gitdir").write_text(
            f"{wt_path / '.git'}\n", encoding="utf-8", errors="surrogateescape"
        )
        (wt_path / ".git").write_text(
            f"gitdir: {os.path.relpath(gitdir, wt_path)}\n",
            encoding="utf-8",
            errors="surrogateescape",
        )
    else:
        (gitdir / "commondir").write_text(f"{git_base}\n", encoding="utf-8")
        (gitdir / "gitdir").write_text(
            f"{wt_path / '.git'}\n", encoding="utf-8", errors="surrogateescape"
        )
        (wt_path / ".git").write_text(
            f"gitdir: {gitdir}\n", encoding="utf-8", errors="surrogateescape"
        )


@pytest.fixture
def workspace_with_worktrees(tmp_path: Path) -> Workspace:
    """A checkout with a nested and an outside linked worktree, a submodule and a clone."""
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    (main / ".gitignore").write_text(".claude/\nrepos/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text('[project]\nname = "main"\n', encoding="utf-8")

    library = tmp_path / "library"
    (library / ".git").mkdir(parents=True)
    (library / "README.md").write_text("library\n", encoding="utf-8")

    nested = main / ".claude" / "worktrees" / "wt"
    _make_worktree(main, nested, "wt")

    outside = tmp_path / "worktrees" / "outside"
    _make_worktree(main, outside, "outside")

    submodule = main / "libs" / "sub"
    submodule.mkdir(parents=True)
    sub_gitdir = main / ".git" / "modules" / "libs" / "sub"
    sub_gitdir.mkdir(parents=True)
    (submodule / ".git").write_text(f"gitdir: {sub_gitdir}\n", encoding="utf-8")
    (main / ".gitmodules").write_text(
        '[submodule "libs/sub"]\n\tpath = libs/sub\n\turl = ../library\n', encoding="utf-8"
    )

    clone = main / "repos" / "org" / "name"
    clone.mkdir(parents=True)
    (clone / ".git").mkdir(parents=True)
    (clone / "README.md").write_text("library\n", encoding="utf-8")
    return Workspace(main, nested, outside, submodule, clone)


def test_a_worktree_outside_the_checkout_checks_itself(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify a linked worktree outside the checkout and its subdirectory resolve to it."""
    outside = workspace_with_worktrees.outside
    (outside / "src").mkdir()

    roots = (find_worktree_root(outside), find_worktree_root(outside / "src"))

    assert roots == (outside.resolve(),) * 2


def test_a_submodule_shares_the_workspace_data(workspace_with_worktrees: Workspace) -> None:
    """Verify a real submodule, whose git directory has no `commondir`, resolves its workspace
    root and data directory to the checkout that holds it."""
    submodule = workspace_with_worktrees.submodule

    roots = (find_top_level_repo_root(submodule), main_worktree_root(submodule))

    assert roots == (workspace_with_worktrees.main.resolve(),) * 2


def test_a_clone_under_repos_resolves_to_the_workspace(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify a repository cloned under `repos/` still resolves to the devops-cli workspace."""
    clone = workspace_with_worktrees.clone
    (clone / "docs").mkdir()

    roots = (
        find_worktree_root(clone),
        find_worktree_root(clone / "docs"),
        find_top_level_repo_root(clone),
    )

    assert roots == (workspace_with_worktrees.main.resolve(),) * 3


def test_a_clone_inside_a_nested_worktree_resolves_to_that_worktree(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify the nearest linked worktree wins over the checkout around it."""
    nested = workspace_with_worktrees.nested
    clone = nested / "repos" / "org" / "x"
    clone.mkdir(parents=True)
    (clone / ".git").mkdir(parents=True)
    (clone / "README.md").write_text("library\n", encoding="utf-8")

    assert find_worktree_root(clone) == nested.resolve()


def test_a_file_path_resolves_to_its_worktree(workspace_with_worktrees: Workspace) -> None:
    """Verify a file inside a nested worktree resolves to that worktree."""
    nested = workspace_with_worktrees.nested
    module = nested / "module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")

    assert find_worktree_root(module) == nested.resolve()


def test_a_worktree_with_a_relative_gitdir_checks_itself(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify a worktree added with `--relative-paths` resolves to itself."""
    main = workspace_with_worktrees.main
    relative = main / ".claude" / "worktrees" / "rel"
    _make_worktree(main, relative, "rel", relative=True)

    assert find_worktree_root(relative) == relative.resolve()


def test_the_top_level_root_still_climbs_out_of_a_nested_worktree(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify the workspace resolver keeps its top-most rule; only verifying commands differ."""
    nested = workspace_with_worktrees.nested

    assert find_top_level_repo_root(nested) == workspace_with_worktrees.main.resolve()


def test_worktrees_of_a_clone_under_repos_resolve_to_the_workspace(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify a clone's own worktrees, beside it or nested in it, resolve with the clone."""
    clone = workspace_with_worktrees.clone
    beside = clone.parent / "name-wt"
    nested = clone / ".claude" / "worktrees" / "x"
    _make_worktree(clone, beside, "beside")
    _make_worktree(clone, nested, "nested")

    roots = (find_worktree_root(beside), find_worktree_root(nested))

    assert roots == (workspace_with_worktrees.main.resolve(),) * 2


def test_a_pruned_nested_worktree_still_checks_itself(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify a nested worktree whose git directory was deleted is flagged, not climbed out of."""
    main, nested = workspace_with_worktrees.main, workspace_with_worktrees.nested
    shutil.rmtree(main / ".git" / "worktrees" / "wt")

    assert (
        find_worktree_root(nested),
        is_stale_linked_worktree(nested),
        main_worktree_root(nested),
    ) == (nested.resolve(), True, main.resolve())


def test_a_nested_worktree_of_a_moved_checkout_still_checks_itself(
    workspace_with_worktrees: Workspace, tmp_path: Path
) -> None:
    """Verify a nested worktree whose `.git` file names the checkout's old path checks itself,
    as when a checkout's path differs between a devcontainer and its host, and shares the moved
    checkout's data directory."""
    moved = tmp_path / "moved"
    workspace_with_worktrees.main.rename(moved)
    nested = moved / ".claude" / "worktrees" / "wt"

    assert (
        find_worktree_root(nested),
        is_stale_linked_worktree(nested),
        main_worktree_root(nested),
    ) == (nested.resolve(), True, moved.resolve())


def test_live_worktrees_submodules_and_checkouts_are_not_stale(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify only a `.git` file naming a missing worktree git directory counts as stale."""
    workspace = workspace_with_worktrees
    roots = (workspace.main, workspace.nested, workspace.outside, workspace.submodule)

    assert [is_stale_linked_worktree(root) for root in roots] == [False] * 4


def test_a_submodule_with_a_missing_git_directory_resolves_to_the_workspace(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify only a missing `worktrees/<name>` directory marks a stale worktree; a submodule
    whose module directory is gone keeps climbing to the workspace."""
    main, submodule = workspace_with_worktrees.main, workspace_with_worktrees.submodule
    shutil.rmtree(main / ".git" / "modules" / "libs" / "sub")

    assert (find_worktree_root(submodule), is_stale_linked_worktree(submodule)) == (
        main.resolve(),
        False,
    )


def test_worktrees_of_a_bare_repository_check_themselves(tmp_path: Path) -> None:
    """Verify the worktrees of a `.bare` clone, whose container's `.git` file names it,
    resolve to themselves rather than to the container, which holds no project."""
    container = tmp_path / "proj"
    bare = container / ".bare"
    bare.mkdir(parents=True)
    (bare / "config").write_text("[core]\n\tbare = true\n", encoding="utf-8")
    (container / ".git").write_text("gitdir: ./.bare\n", encoding="utf-8")
    feature, other = container / "feature", container / "other"
    _make_worktree(bare, feature, "feature")
    _make_worktree(bare, other, "other")
    (feature / "src").mkdir()

    roots = [find_worktree_root(path) for path in (feature, feature / "src", other)]

    assert roots == [feature.resolve(), feature.resolve(), other.resolve()]


def test_a_worktree_of_a_checkout_inside_another_repository_checks_itself(
    tmp_path: Path,
) -> None:
    """Verify a nested worktree of a checkout that lies below another repository, such as a
    dotfiles repository at `$HOME`, checks itself and resolves to its own repository (#617)."""
    outer = tmp_path / "outer"
    (outer / ".git").mkdir(parents=True)
    checkout = outer / "src" / "proj"
    (checkout / ".git").mkdir(parents=True)
    nested = checkout / ".claude" / "worktrees" / "wt"
    _make_worktree(checkout, nested, "wt")

    assert (
        find_worktree_root(nested),
        main_worktree_root(nested),
        find_top_level_repo_root(nested),
        find_worktree_root(checkout),
        main_worktree_root(checkout),
        find_top_level_repo_root(checkout),
    ) == (
        nested.resolve(),
        checkout.resolve(),
        checkout.resolve(),
        checkout.resolve(),
        checkout.resolve(),
        checkout.resolve(),
    )


def test_a_worktree_of_a_repository_outside_the_workspace_checks_itself(
    workspace_with_worktrees: Workspace, tmp_path: Path
) -> None:
    """Verify a live worktree of an external repository, nested in the workspace, and its
    subdirectory check that worktree and resolve to their own repository, not the workspace
    around them (#617)."""
    main = workspace_with_worktrees.main
    external = main / ".claude" / "worktrees" / "lib"
    _make_worktree(tmp_path / "library", external, "ext")
    (external / "sub").mkdir()

    roots = (
        find_worktree_root(external),
        find_worktree_root(external / "sub"),
        main_worktree_root(external),
        main_worktree_root(external / "sub"),
    )

    library = (tmp_path / "library").resolve()
    assert roots == (external.resolve(),) * 2 + (library,) * 2


def test_deeply_nested_unrelated_checkouts_and_worktrees_resolve_to_own_repositories(
    tmp_path: Path,
) -> None:
    """Verify checkouts and worktrees nested at multiple levels resolve to their own repositories,
    regardless of how many unrelated repositories or projects enclose them (#617)."""
    outer = tmp_path / "outer"
    (outer / ".git").mkdir(parents=True)

    middle = outer / "sub" / "middle"
    (middle / ".git").mkdir(parents=True)

    inner = middle / "vendor" / "inner"
    (inner / ".git").mkdir(parents=True)

    worktree = inner / ".worktrees" / "wt"
    _make_worktree(inner, worktree, "wt")

    assert (
        find_top_level_repo_root(worktree),
        find_worktree_root(worktree),
        main_worktree_root(worktree),
    ) == (inner.resolve(), worktree.resolve(), inner.resolve())

    assert (
        find_top_level_repo_root(inner),
        find_worktree_root(inner),
        main_worktree_root(inner),
    ) == (inner.resolve(), inner.resolve(), inner.resolve())

    assert (
        find_top_level_repo_root(middle),
        find_worktree_root(middle),
        main_worktree_root(middle),
    ) == (middle.resolve(), middle.resolve(), middle.resolve())

    assert (
        find_top_level_repo_root(outer),
        find_worktree_root(outer),
        main_worktree_root(outer),
    ) == (outer.resolve(), outer.resolve(), outer.resolve())


def test_an_undecodable_git_file_resolves_to_the_workspace(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify a `.git` file, or a `commondir` it leads to, holding bytes that are not UTF-8
    names no worktree, so the climb continues to the workspace instead of raising."""
    main = workspace_with_worktrees.main
    garbled = main / ".claude" / "worktrees" / "garbled"
    garbled.mkdir(parents=True)
    (garbled / ".git").write_bytes(b"gitdir: \xff\xfe\n")
    bad_gitdir = main / ".git" / "worktrees" / "bad"
    bad_gitdir.mkdir()
    (bad_gitdir / "commondir").write_bytes(b"\xff\n")
    bad_common = main / ".claude" / "worktrees" / "bad"
    bad_common.mkdir()
    (bad_common / ".git").write_text(f"gitdir: {bad_gitdir}\n", encoding="utf-8")

    roots = (find_worktree_root(garbled), find_worktree_root(bad_common))

    assert roots == (main.resolve(),) * 2


def test_a_worktree_whose_path_is_not_utf8_checks_itself(
    workspace_with_worktrees: Workspace,
) -> None:
    """Verify a worktree at a path holding Latin-1 bytes, which git writes into its `.git`
    file unchanged, is still recognised as a live linked worktree of its main checkout."""
    latin1 = workspace_with_worktrees.main / ".claude" / "worktrees" / os.fsdecode(b"caf\xe9")
    latin1.mkdir(parents=True)
    _make_worktree(workspace_with_worktrees.main, latin1, "latin1")

    assert (
        find_worktree_root(latin1),
        is_stale_linked_worktree(latin1),
        main_worktree_root(latin1),
    ) == (latin1.resolve(), False, workspace_with_worktrees.main.resolve())


def test_core_repo_gitignore_and_files(tmp_path: Path, git_fake: GitFake) -> None:
    """Verify gitignore parsing and listing repo files."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    git_fake.answer(lambda c: "ls-files" in c.argv, ProcessAnswer(returncode=1))
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
    call_count_before = len(git_fake.calls)
    assert is_ignored_by_git(tmp_path, tmp_path / "dynamic_ignored.txt") is False
    assert len(git_fake.calls) == call_count_before

    # A rule added after the first evaluation takes effect once the cache is reset.
    # Compiled ignore files are revalidated on an interval rather than stat-ed per call,
    # which is what makes a repository walk affordable.
    (tmp_path / ".gitignore").write_text("*.tmp\nbuild/\ndynamic_ignored.txt\n", encoding="utf-8")
    reset_indexes()
    assert is_ignored_by_git(tmp_path, tmp_path / "dynamic_ignored.txt") is True

    # Symlink outside repository root
    outside_dir = tmp_path.parent / f"outside_{tmp_path.name}"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    try:
        outside_file.write_text("secret", encoding="utf-8")

        symlink_file = tmp_path / "linked_secret.txt"
        try:
            symlink_file.symlink_to(outside_file)
        except OSError:
            pass

        listed_files = list_repo_files(tmp_path)
        assert outside_file not in listed_files
    finally:
        outside_file.unlink(missing_ok=True)
        if outside_dir.exists():
            outside_dir.rmdir()


def test_repos_branch_and_workspace_helpers(tmp_path: Path, git_fake: GitFake) -> None:
    """Verify _current_branch and _resolve_workspace_file."""
    from devops_cli.commands.repos import _current_branch, _resolve_workspace_file
    from devops_cli.config.constants import CONST_VSCODE_WORKSPACE_FILE

    git_fake.answer(
        lambda c: "branch" in c.argv and "--show-current" in c.argv,
        ProcessAnswer(returncode=128, stderr="fatal: not a git repository"),
    )
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
        assert res_err.exit_code == 1


def test_repos_sync_reports_failures_and_exits_nonzero(tmp_path: Path, git_fake: GitFake) -> None:
    """`repos sync` reports failed repos with git's reason, finishes remaining repos, and exits 1."""
    repos_dir = tmp_path / "repos"
    repo1 = repos_dir / "group" / "repo1"
    repo2 = repos_dir / "group" / "repo2"
    for repo in (repo1, repo2):
        (repo / ".git").mkdir(parents=True)
    git_fake.answer(["git", "-C", str(repo1), "remote"], ProcessAnswer(stdout="origin\n"))
    git_fake.answer(["git", "-C", str(repo2), "remote"], ProcessAnswer(stdout="origin\n"))
    git_fake.answer(
        ["git", "-C", str(repo1), "fetch"],
        ProcessAnswer(returncode=128, stderr="fatal: Could not read from remote repository.\n"),
    )
    git_fake.answer(["git", "-C", str(repo2), "fetch"], ProcessAnswer())
    git_fake.answer(["git", "-C", str(repo2), "branch"], ProcessAnswer(stdout="main\n"))
    git_fake.answer(["git", "-C", str(repo2), "config"], ProcessAnswer(stdout="origin\n"))
    git_fake.answer(["git", "-C", str(repo2), "pull"], ProcessAnswer())

    res = runner.invoke(repos_app, ["sync", "--base-dir", str(repos_dir)])

    assert (
        res.exit_code,
        "group/repo1" in res.output,
        "Could not read from remote repository" in res.output,
        "group/repo2" in res.output,
    ) == (1, True, True, True)


def test_core_repo_safe_paths_and_tracked_files(tmp_path: Path, git_fake: GitFake) -> None:
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
    (base / ".git").mkdir()
    (base / "src").mkdir()
    (base / "src" / "app.py").write_text("code", encoding="utf-8")
    (base / "README.md").write_text("docs", encoding="utf-8")
    (base / "image.png").write_text("binary", encoding="utf-8")

    git_fake.answer(
        lambda c: "ls-files" in c.argv,
        ProcessAnswer(stdout="src/app.py\nREADME.md\nimage.png\n"),
    )
    tracked = _list_git_tracked_files(base, base)
    assert tracked is not None
    assert base / "src" / "app.py" in tracked
    assert base / "image.png" not in tracked  # binary filtered

    # 3. list_repo_files for single file, missing target, and directory walk fallback
    single_f = base / "src" / "app.py"
    files = list_repo_files(single_f)
    assert files == [single_f]

    assert list_repo_files(tmp_path / "non_existent_folder") == []

    git_fake.answer(lambda c: "ls-files" in c.argv, ProcessAnswer(returncode=1))
    walked = list_repo_files(base)
    assert base / "src" / "app.py" in walked

    # 4. get_repo_origin_name parsing
    from devops_cli.core.repo import get_repo_origin_name

    get_repo_origin_name.cache_clear()
    git_fake.answer(
        lambda c: "remote" in c.argv,
        ProcessAnswer(stdout="git@github.com:dan-petty/devops-cli.git\n"),
    )
    ssh_origin = get_repo_origin_name(base)

    get_repo_origin_name.cache_clear()
    git_fake.answer(
        lambda c: "remote" in c.argv,
        ProcessAnswer(stdout="https://github.com/dan-petty/devops-cli\n"),
    )
    https_origin = get_repo_origin_name(base)

    assert (ssh_origin, https_origin) == ("dan-petty/devops-cli", "dan-petty/devops-cli")


def test_repo_files_stay_inside_the_checkout_through_links(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """The files git lists are listed only where their real path is in the checkout.

    A tracked directory that the working tree replaced with a link to outside the checkout
    would bring files from outside into a review; a link to a file inside stays listed.
    """
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    (repo / ".git").mkdir(parents=True)
    (repo / "top.py").write_text("top = 1\n", encoding="utf-8")
    outside.mkdir()
    (outside / "a.py").write_text("secret = 1\n", encoding="utf-8")
    (repo / "pkg").symlink_to(outside, target_is_directory=True)
    (repo / "link.py").symlink_to(repo / "top.py")

    git_fake.answer(
        lambda c: "ls-files" in c.argv,
        ProcessAnswer(stdout="link.py\0pkg/a.py\0top.py\0"),
    )

    assert list_repo_files(repo) == [repo / "link.py", repo / "top.py"]


def test_repo_edge_cases(tmp_path: Path, git_fake: GitFake) -> None:
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
    git_fake.answer(["git"], ProcessAnswer(side_effect=Exception("git error")))
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

    git_fake.answer(["git", "ls-files"], ProcessAnswer(returncode=1))
    files = list_repo_files(root)
    assert all("secret.txt" not in str(f) for f in files)

    # 5. is_safe_subpath with exception
    with patch.object(Path, "resolve", side_effect=Exception("resolve error")):
        assert is_safe_subpath(root, "any/path") is False


def test_repos_reload_workspace_and_resolve(tmp_path: Path, process_fake: ProcessFake) -> None:
    """Verify _reload_workspace handles success and failure, and _resolve_workspace_file returns expected paths."""
    from devops_cli.commands.repos import _reload_workspace, _resolve_workspace_file

    ws_file = tmp_path / "test.code-workspace"
    ws_file.write_text("{}", encoding="utf-8")

    # Success
    process_fake.answer(["code"], ProcessAnswer(returncode=0))
    _reload_workspace(ws_file)

    # Subprocess failure handles exception safely
    process_fake.answer(["code"], ProcessAnswer(side_effect=OSError("not found")))
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


def test_repos_clone_org_missing_org() -> None:
    """Verify clone-org stops when no organization is given or configured."""
    with patch("devops_cli.commands.repos.load_settings") as mock_load:
        settings = MagicMock()
        settings.github.default_org = None
        mock_load.return_value = settings
        res = runner.invoke(app, ["repos", "clone-org"])
        assert res.exit_code == 1


def test_a_directory_with_no_repository_has_no_origin_whatever_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """The lookup reads the origin remote of the root that the caller gives, and nothing else:
    `GITHUB_REPOSITORY` names no repository for a directory that holds none (#2127)."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "example-org/app")
    assert (get_repo_origin_name(tmp_path), process_fake.calls) == (None, [])


def test_repo_origin_lru_caching(tmp_path: Path, git_fake: GitFake) -> None:
    """Verify get_repo_origin_name caches subsequent lookups for the same repo root."""
    from devops_cli.core.repo import get_repo_origin_name

    (tmp_path / ".git").mkdir()
    git_fake.answer(
        ["git", "remote", "get-url", "origin"],
        ProcessAnswer(stdout="git@github.com:org/cached-repo.git\n"),
    )
    get_repo_origin_name.cache_clear()
    res1 = get_repo_origin_name(tmp_path)
    res2 = get_repo_origin_name(tmp_path)
    remote_calls = [c for c in git_fake.calls if "remote" in c.argv]
    assert (res1, res2, len(remote_calls)) == ("org/cached-repo", "org/cached-repo", 1)


def test_list_repo_files_handles_spaces_non_ascii_and_renames(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """Real git repository file listing includes unquoted non-ASCII files and files with spaces."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    (repo / "first.py").write_text("a = 1\n", encoding="utf-8")
    (repo / "path with space.py").write_text("c = 3\n", encoding="utf-8")
    (repo / "café.py").write_text("d = 4\n", encoding="utf-8")
    (repo / "renamed.py").write_text("b = 2\n", encoding="utf-8")

    git_fake.answer(
        lambda c: "ls-files" in c.argv,
        ProcessAnswer(stdout="café.py\0first.py\0path with space.py\0renamed.py\0"),
    )

    files = list_repo_files(repo)
    expected = [
        repo / "café.py",
        repo / "first.py",
        repo / "path with space.py",
        repo / "renamed.py",
    ]
    assert files == expected


# =============================================================================
# Dry runs (#2258)
# =============================================================================


def _answer_tracking_repo(git_fake: GitFake, repo_dir: Path) -> None:
    """Git answers for a repository whose `main` tracks `origin`."""
    (repo_dir / ".git").mkdir(parents=True)
    git_fake.answer(["git", "-C", str(repo_dir), "remote"], ProcessAnswer(stdout="origin\n"))
    git_fake.answer(
        ["git", "-C", str(repo_dir), "branch", "--show-current"], ProcessAnswer(stdout="main\n")
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(["git", "-C", str(repo_dir), "fetch"], ProcessAnswer())
    git_fake.answer(["git", "-C", str(repo_dir), "pull"], ProcessAnswer())


def _sync_workspace(
    tmp_path: Path, git_fake: GitFake, config: Callable[..., Path]
) -> tuple[Path, list[Path], Path]:
    """A workspace with two repositories, and the workspace file of the settings."""
    repos_dir = (tmp_path / "repos").resolve()
    repo_dirs = [repos_dir / "group" / "alpha", repos_dir / "group" / "beta"]
    for repo_dir in repo_dirs:
        _answer_tracking_repo(git_fake, repo_dir)
    ws_file = tmp_path / "ws.code-workspace"
    config(workspace={"file": str(ws_file)})
    return repos_dir, repo_dirs, ws_file


def _external_calls(fake: ProcessFake) -> list[str]:
    """Each recorded command that is not a read of the local repository, as one line."""
    return [" ".join(call.argv) for call in fake.calls if not call.local_read]


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    import re

    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


def test_repos_dry_run_classes() -> None:
    """Each repos command carries the dry-run class of what it reaches."""
    from devops_cli.commands import repos
    from devops_cli.dry_run.decorator import get_dry_run_class

    for callback in (repos.update, repos.worktrees_prune, repos.clone, repos.clone_org):
        assert get_dry_run_class(callback) == "request-plan"
    for callback in (repos.list_repos, repos.worktrees_status):
        assert get_dry_run_class(callback) == "no-external-request"


@pytest.mark.parametrize(
    "argv",
    [
        ["repos", "sync", "--dry-run"],
        ["repos", "update", "--dry-run"],
        ["--dry-run", "repos", "sync"],
    ],
)
def test_repos_sync_dry_run_lists_the_fetches_pulls_and_reload(
    tmp_path: Path,
    git_fake: GitFake,
    config: Callable[..., Path],
    cli: Callable[..., Any],
    argv: list[str],
) -> None:
    """A dry run reads the local repositories, makes no request, and lists the requests."""
    repos_dir, (alpha, beta), ws_file = _sync_workspace(tmp_path, git_fake, config)

    result = cli([*argv, "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert _external_calls(git_fake) == []
    assert not ws_file.exists()
    assert _plan_lines(result.output) == [
        f"git -C {alpha} fetch --prune origin",
        f"git -C {alpha} pull origin main",
        f"git -C {beta} fetch --prune origin",
        f"git -C {beta} pull origin main",
        f"code --reuse-window -- {ws_file}",
    ]


def test_repos_sync_dry_run_without_pull_lists_no_pull(
    tmp_path: Path, git_fake: GitFake, config: Callable[..., Path], cli: Callable[..., Any]
) -> None:
    """`--no-pull` leaves the pulls out of the plan, as it leaves them out of the run."""
    repos_dir, _repo_dirs, _ws_file = _sync_workspace(tmp_path, git_fake, config)

    result = cli(["--dry-run", "repos", "update", "--no-pull", "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert not [line for line in _plan_lines(result.output) if " pull " in line]


def test_repos_sync_runs_the_requests_of_its_plan(
    tmp_path: Path, git_fake: GitFake, config: Callable[..., Path], cli: Callable[..., Any]
) -> None:
    """The real run starts the commands of the plan, in the same order."""
    repos_dir, _repo_dirs, _ws_file = _sync_workspace(tmp_path, git_fake, config)
    planned = _plan_lines(cli(["repos", "sync", "--dry-run", "--base-dir", str(repos_dir)]).output)
    git_fake.calls.clear()

    result = cli(["repos", "sync", "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert _external_calls(git_fake) == planned


def test_repos_list_runs_under_the_dry_run_flag(
    tmp_path: Path, git_fake: GitFake, cli: Callable[..., Any]
) -> None:
    """`repos list` reads only the local repositories, so `devops --dry-run` runs it."""
    repos_dir = (tmp_path / "repos").resolve()
    repo_dir = repos_dir / "group" / "alpha"
    _answer_tracking_repo(git_fake, repo_dir)

    result = cli(["--dry-run", "repos", "list", "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert "alpha" in result.output
    assert "main" in result.output
    assert _external_calls(git_fake) == []


def test_repos_list_has_no_dry_run_option(cli: Callable[..., Any]) -> None:
    """`repos list` makes no request, so it has no preview to offer."""
    result = cli(["repos", "list", "--dry-run"])

    assert result.exit_code == 2
    assert "No such option" in result.output


_CLONE_URL = "https://github.com/example-org/app.git"


@pytest.mark.parametrize(
    "argv",
    [
        ["repos", "clone", _CLONE_URL, "--dry-run"],
        ["--dry-run", "repos", "clone", _CLONE_URL],
    ],
)
def test_repos_clone_dry_run_lists_the_clone_and_reload(
    tmp_path: Path,
    git_fake: GitFake,
    known_hosts: Path,
    config: Callable[..., Path],
    cli: Callable[..., Any],
    argv: list[str],
) -> None:
    """A dry run clones nothing, writes no host key, and lists the clone and the reload."""
    repos_dir = (tmp_path / "repos").resolve()
    repos_dir.mkdir()
    ws_file = tmp_path / "ws.code-workspace"
    config(workspace={"file": str(ws_file)})

    result = cli([*argv, "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert git_fake.calls == []
    assert list(repos_dir.iterdir()) == []
    assert not known_hosts.exists()
    assert _plan_lines(result.output) == [
        f"git clone -- {_CLONE_URL} {repos_dir / 'example-org' / 'app'}",
        f"code --reuse-window -- {ws_file}",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["repos", "clone", "--dry-run", "--", "-bad"],
        ["--dry-run", "repos", "clone", "--", "-bad"],
    ],
)
def test_repos_clone_dry_run_refuses_what_a_run_refuses(
    git_fake: GitFake, cli: Callable[..., Any], argv: list[str]
) -> None:
    """A URL that starts with a hyphen ends the dry run as it ends the run."""
    result = cli(argv)

    assert result.exit_code == 1
    assert "Invalid repository URL: must not start with a hyphen." in result.output
    assert _plan_lines(result.output) == []


def test_repos_clone_runs_the_requests_of_its_plan(
    tmp_path: Path,
    git_fake: GitFake,
    known_hosts: Path,
    config: Callable[..., Path],
    cli: Callable[..., Any],
) -> None:
    """The real run starts the commands of the plan, in the same order."""
    repos_dir = (tmp_path / "repos").resolve()
    repos_dir.mkdir()
    config(workspace={"file": str(tmp_path / "ws.code-workspace")})
    git_fake.answer(["git", "clone"], ProcessAnswer())
    argv = ["repos", "clone", _CLONE_URL, "--base-dir", str(repos_dir)]
    planned = _plan_lines(cli([*argv, "--dry-run"]).output)

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert _external_calls(git_fake) == planned


@pytest.mark.parametrize(
    "argv",
    [
        ["repos", "clone-org", "example-org", "--dry-run"],
        ["--dry-run", "repos", "clone-org", "example-org"],
    ],
)
def test_repos_clone_org_dry_run_lists_the_listing_and_the_clones(
    tmp_path: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    cli: Callable[..., Any],
    argv: list[str],
) -> None:
    """A dry run sends GitHub nothing, starts nothing, and lists the requests of the run."""
    repos_dir = (tmp_path / "repos").resolve()
    ws_file = tmp_path / "ws.code-workspace"
    config(workspace={"file": str(ws_file)})

    result = cli([*argv, "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert (github_api.requested, process_fake.calls) == ([], [])
    assert not repos_dir.exists()
    lines = _plan_lines(result.output)
    assert lines[0] == f"GET {_ORG_REPOS}  [repeated for each next page of the listing]"
    assert lines[1].startswith("GET /user  [only if GitHub answers 404")
    assert lines[2].startswith("GET /user/repos?affiliation=owner&visibility=all")
    assert lines[3].startswith(
        "git clone -- 'https://github.com/<owner>/<repo>.git' "
        f"'{repos_dir / 'example-org' / '<repo>'}'"
    )
    assert "[repeated for each listed repository" in lines[3]
    assert lines[4] == f"code --reuse-window -- {ws_file}"


def test_repos_clone_org_dry_run_refuses_a_path_traversal(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """An organization name that leaves the base directory ends the dry run as it ends a run."""
    result = cli(["repos", "clone-org", "../escaped-org", "--dry-run"])

    assert (result.exit_code, github_api.requested) == (1, [])


def test_repos_clone_org_runs_the_requests_of_its_plan(
    tmp_path: Path,
    git_fake: GitFake,
    known_hosts: Path,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    cli: Callable[..., Any],
) -> None:
    """The run reads the listing of the plan, then clones the one listed repository."""
    active_repo = _recorded_repositories()[0]
    github_api.route("GET", _ORG_REPOS, github_json([active_repo]))
    git_fake.answer(["git", "clone"], ProcessAnswer())
    repos_dir = (tmp_path / "repos").resolve()
    config(workspace={"file": str(tmp_path / "ws.code-workspace")})
    argv = ["repos", "clone-org", "example-org", "--base-dir", str(repos_dir)]
    planned = cli([*argv, "--dry-run"]).output

    result = cli(argv)

    assert result.exit_code == 0, result.output
    lines = _plan_lines(planned)
    assert github_api.requested == [f"GET https://api.github.com{lines[0].split()[1]}"]
    dest = repos_dir / "example-org" / active_repo["name"]
    clone_line = lines[3].split("  [")[0]
    clone_line = clone_line.replace(
        "'https://github.com/<owner>/<repo>.git'", active_repo["clone_url"]
    )
    clone_line = clone_line.replace(f"'{repos_dir / 'example-org' / '<repo>'}'", str(dest))
    assert _external_calls(git_fake) == [clone_line, lines[4]]
