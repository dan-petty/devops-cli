"""One data directory across git worktrees (#553).

A relative data directory resolved against the current worktree, so each worktree kept its own
reviews, benchmarks and evaluations, and removing it deleted them: the first full sample
validation (#505) was lost that way. Linked worktrees now resolve to the main worktree, and
repositories cloned under the workspace's `repos/` keep sharing the workspace's (#582).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.analyze.cache import (
    analysis_directory,
    load_cached_analysis,
    save_analysis_metadata,
)
from devops_cli.ai.benchmark.suite import load_feedback_benchmark_dataset
from devops_cli.ai.model_bundler import bundle_ollama_models
from devops_cli.ai.prompt_eval import evaluate_persona_prompts
from devops_cli.ai.review.common_hallucinations import get_common_hallucinations_file_path
from devops_cli.ai.review.review_environment import _get_reviews_base_dir
from devops_cli.commands.ai import app as ai_app
from devops_cli.commands.workspace import app as workspace_app
from devops_cli.config.constants import CONST_HALLUCINATIONS_FILE_NAME
from devops_cli.core.cleanup import cleanup_data_tier
from devops_cli.core.repo import main_worktree_root, resolve_data_path
from devops_cli.exceptions import SecurityError
from devops_cli.server.routes.workspace import list_workspaces

_A_FORTNIGHT_AGO = time.time() - 14 * 86400


@pytest.fixture
def init_repo(git: Callable[..., None]) -> Callable[[Path], Path]:
    """Create a repository with one commit at a given path, so worktrees can be added to it."""

    def init(main: Path) -> Path:
        main.mkdir(parents=True)
        git(main, "init", "--quiet")
        (main / "README.md").write_text("project\n", encoding="utf-8")
        git(main, "add", ".")
        git(main, "commit", "--quiet", "-m", "first")
        return main

    return init


@pytest.fixture
def repo_with_worktree(
    tmp_path: Path, git: Callable[..., None], init_repo: Callable[[Path], Path]
) -> tuple[Path, Path]:
    """A repository and a linked worktree of it, outside the repository's own tree."""
    main = init_repo(tmp_path / "project")
    linked = tmp_path / "worktrees" / "feature"
    git(main, "worktree", "add", "--quiet", "-b", "feature", str(linked))
    return main, linked


def _worktree_in_another_workspace(
    tmp_path: Path, git: Callable[..., None], init_repo: Callable[[Path], Path], marker: str
) -> tuple[Path, Path]:
    """A repository and a linked worktree of it inside another workspace (the worktree's parent),
    a directory holding its own `.git` or `pyproject.toml`, where a search for the top-most
    workspace root starting at the worktree stops."""
    main = init_repo(tmp_path / "project")
    host = tmp_path / "host"
    host.mkdir()
    if marker == "git":
        git(host, "init", "--quiet")
    else:
        (host / "pyproject.toml").write_text("[project]\nname = 'host'\n", encoding="utf-8")
    linked = host / "feature"
    git(main, "worktree", "add", "--quiet", "-b", "feature", str(linked))
    return main, linked


@pytest.fixture
def repo_with_worktree_in_another_repository(
    tmp_path: Path, git: Callable[..., None], init_repo: Callable[[Path], Path]
) -> tuple[Path, Path]:
    """A repository and a linked worktree of it inside an unrelated git repository."""
    return _worktree_in_another_workspace(tmp_path, git, init_repo, "git")


@pytest.fixture
def repo_with_worktree_in_a_python_project(
    tmp_path: Path, git: Callable[..., None], init_repo: Callable[[Path], Path]
) -> tuple[Path, Path]:
    """A repository and a linked worktree of it inside a directory holding `pyproject.toml`."""
    return _worktree_in_another_workspace(tmp_path, git, init_repo, "pyproject")


_WORKTREES_IN_ANOTHER_WORKSPACE = [
    "repo_with_worktree_in_another_repository",
    "repo_with_worktree_in_a_python_project",
]

_OUTER_DIRECTORY_LIMIT = pytest.mark.xfail(
    strict=True,
    reason=(
        "Known limit (#585): a checkout or worktree below another directory holding .git or "
        "pyproject.toml resolves shared data to that outer directory"
    ),
)
"""Marks a case of that limit: data resolves to the outer directory, not the main worktree."""


def test_a_linked_worktree_resolves_to_the_main_worktree(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    """Verify the main worktree is found from the main one, a linked one and a subdirectory."""
    main, linked = repo_with_worktree
    (linked / "src").mkdir()

    roots = (
        main_worktree_root(main),
        main_worktree_root(linked),
        main_worktree_root(linked / "src"),
    )

    assert roots == (main.resolve(),) * 3


def test_nested_linked_worktree_resolves_to_the_main_worktree(
    nested_worktree: tuple[Path, Path],
) -> None:
    """Verify a linked worktree nested inside the main checkout resolves to the main worktree."""
    main, nested = nested_worktree
    (nested / "src").mkdir()

    roots = (
        main_worktree_root(nested),
        main_worktree_root(nested / "src"),
        resolve_data_path(Path(".data/reviews"), nested),
    )
    expected = (
        main.resolve(),
        main.resolve(),
        (main / ".data" / "reviews").resolve(),
    )
    assert roots == expected


def test_a_nested_worktree_with_a_relative_gitdir_resolves_to_the_main_worktree(
    nested_worktree: tuple[Path, Path], git: Callable[..., None]
) -> None:
    """Verify a nested worktree added with `--relative-paths` shares the main worktree."""
    main, _ = nested_worktree
    relative = main / ".claude" / "worktrees" / "relative"
    try:
        git(main, "worktree", "add", "--quiet", "--relative-paths", "-b", "rel", str(relative))
    except subprocess.CalledProcessError:
        pytest.skip("git does not support `worktree add --relative-paths`")

    assert main_worktree_root(relative) == main.resolve()


def test_a_pruned_nested_worktree_shares_the_main_worktree(
    nested_worktree: tuple[Path, Path],
) -> None:
    """Verify a nested worktree whose git directory was pruned still shares the main worktree."""
    main, nested = nested_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "wt")

    assert main_worktree_root(nested) == main.resolve()


def test_a_pruned_worktree_outside_the_checkout_shares_the_main_worktree(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    """Verify a worktree outside the checkout whose git directory was pruned still shares the
    main worktree's data, found through the shared git directory its `.git` file names."""
    main, linked = repo_with_worktree
    shutil.rmtree(main / ".git" / "worktrees" / "feature")

    roots = (main_worktree_root(linked), resolve_data_path(Path(".data"), linked))

    assert roots == (main.resolve(), (main / ".data").resolve())


def test_a_pruned_worktree_of_a_moved_checkout_keeps_its_own_data(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """Verify a stale worktree whose main checkout is gone resolves to itself rather than to a
    directory that no longer holds the repository."""
    main, linked = repo_with_worktree
    main.rename(tmp_path / "moved")

    assert main_worktree_root(linked) == linked.resolve()


def test_a_clone_under_repos_and_its_worktree_share_the_workspace_data(
    nested_worktree: tuple[Path, Path], tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify a repository cloned under `repos/`, and a linked worktree of that clone, keep
    resolving to the workspace's data directory rather than to a directory of their own."""
    main, _ = nested_worktree
    clone = main / "repos" / "org" / "clone"
    git(tmp_path, "clone", "--quiet", str(main), str(clone))
    clone_worktree = main / "repos" / "org" / "clone-wt"
    git(clone, "worktree", "add", "--quiet", "-b", "clone-wt", str(clone_worktree))

    roots = (
        main_worktree_root(clone),
        main_worktree_root(clone_worktree),
        resolve_data_path(Path(".data/reviews"), clone_worktree),
    )

    assert roots == (main.resolve(), main.resolve(), (main / ".data" / "reviews").resolve())


def test_relative_data_paths_are_shared_and_absolute_ones_kept(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """Verify every worktree's relative data path lands in the main worktree's data directory."""
    main, linked = repo_with_worktree

    resolved = (
        resolve_data_path(Path(".data/reviews"), linked),
        resolve_data_path(Path(".data/reviews"), main),
        resolve_data_path(tmp_path / "elsewhere", linked),
    )

    assert resolved == (
        (main / ".data" / "reviews").resolve(),
        (main / ".data" / "reviews").resolve(),
        tmp_path / "elsewhere",
    )


def test_a_git_file_without_a_shared_directory_and_no_git_keep_their_own_root(
    tmp_path: Path,
) -> None:
    """Verify a `.git` file whose git directory has no `commondir` (a submodule's) is not
    followed, and a directory outside git resolves to itself."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    modules = tmp_path / "store" / "modules" / "lib"
    modules.mkdir(parents=True)
    (checkout / ".git").write_text(f"gitdir: {modules}\n", encoding="utf-8")
    plain = tmp_path / "plain"
    plain.mkdir()

    assert (main_worktree_root(checkout), main_worktree_root(plain)) == (
        checkout.resolve(),
        plain.resolve(),
    )


def test_reviews_saved_from_a_worktree_outlive_it(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a review run in a linked worktree saves into the main worktree's data directory."""
    main, linked = repo_with_worktree
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    reviews = _get_reviews_base_dir()

    assert reviews == (main / ".data" / "reviews").resolve()


def test_the_spend_ledger_is_shared_from_any_directory(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the ledger no longer lands under whatever directory the command ran in."""
    from devops_cli.ai.spend.ledger import SpendLedger
    from devops_cli.config.defaults import DEFAULT_AI_SPEND_DB_FILENAME

    main, linked = repo_with_worktree
    (linked / "src").mkdir()
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked / "src")

    ledger = SpendLedger()

    assert ledger.db_path == (main / ".data").resolve() / "ai" / DEFAULT_AI_SPEND_DB_FILENAME


def _stale(path: Path) -> Path:
    """A data file last written a fortnight ago, past the default retention."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    os.utime(path, (_A_FORTNIGHT_AGO, _A_FORTNIGHT_AGO))
    return path


def _write_dataset(path: Path, records: list[dict[str, Any]]) -> None:
    """A feedback dataset in the JSONL shape the review loop appends."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


@pytest.mark.parametrize("start", ["main", "linked"])
def test_workspace_clean_prunes_the_shared_data_directory_from_any_worktree(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, start: str
) -> None:
    """Verify `devops workspace clean` run from a linked worktree prunes the main worktree's data
    rather than finding nothing under a `.data` of its own."""
    main, linked = repo_with_worktree
    stale = _stale(main / ".data" / "reviews" / "old-review.json")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(main if start == "main" else linked)

    summary = cleanup_data_tier()

    assert (summary.pruned_files, stale.exists()) == (["reviews/old-review.json"], False)


def test_workspace_clean_prunes_the_configured_data_directory(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a relative `DEVOPS_CLI_DATA_DIR` is the directory cleaned, under the main worktree."""
    main, linked = repo_with_worktree
    stale = _stale(main / "shared-data" / "logs" / "old.log")
    default_dir_file = _stale(main / ".data" / "logs" / "kept.log")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "shared-data")
    monkeypatch.chdir(linked)

    summary = cleanup_data_tier()

    assert (summary.pruned_files, stale.exists(), default_dir_file.exists()) == (
        ["logs/old.log"],
        False,
        True,
    )


@pytest.mark.parametrize("start", ["main", "linked"])
@pytest.mark.parametrize("configured", ["..", "{parent}", "{home}", "{main}", "/var"])
def test_workspace_clean_refuses_a_data_directory_that_holds_more_than_data(
    repo_with_worktree: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
    start: str,
) -> None:
    """Verify cleanup refuses a data directory that climbs with `..`, or is the main worktree, a
    parent of it, the home directory or a system directory, whose `logs/` and `cache/` are not
    the tool's to prune, whichever worktree it runs from: run from the linked worktree outside
    the main checkout, the main checkout is neither that worktree nor a parent of it."""
    main, linked = repo_with_worktree
    home = tmp_path / "home"
    outside = (
        _stale(tmp_path / "logs" / "app.log"),
        _stale(home / "cache" / "tool" / "f"),
        _stale(main / "logs" / "app.log"),
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(
        "DEVOPS_CLI_DATA_DIR", configured.format(parent=tmp_path, home=home, main=main)
    )
    monkeypatch.chdir(main if start == "main" else linked)

    with pytest.raises(SecurityError, match=r"not a dedicated data directory|traversal"):
        cleanup_data_tier(dry_run=configured == "/var")

    assert [path.exists() for path in outside] == [True, True, True]


@pytest.mark.parametrize("configured", ["{sibling}", "{worktrees}", "{other_repository}"])
def test_workspace_clean_refuses_another_worktree_or_repository(
    repo_with_worktree: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
    git: Callable[..., None],
    init_repo: Callable[[Path], Path],
) -> None:
    """Verify cleanup run from the main checkout refuses a data directory that is a sibling
    linked worktree, the directory holding the linked worktrees, or another repository, whose
    tracked `benchmarks/` and `logs/` are not the tool's to prune."""
    main, linked = repo_with_worktree
    sibling = linked.parent / "sibling"
    git(main, "worktree", "add", "--quiet", "-b", "sibling", str(sibling))
    other_repository = init_repo(tmp_path / "other")
    tracked = (
        _stale(sibling / "benchmarks" / "keep.py"),
        _stale(linked / "logs" / "tracked.log"),
        _stale(other_repository / "logs" / "tracked.log"),
    )
    monkeypatch.setenv(
        "DEVOPS_CLI_DATA_DIR",
        configured.format(
            sibling=sibling, worktrees=linked.parent, other_repository=other_repository
        ),
    )
    monkeypatch.chdir(main)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier()

    assert [path.exists() for path in tracked] == [True, True, True]


def test_workspace_clean_refuses_a_parent_of_the_main_checkout_without_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    git: Callable[..., None],
    init_repo: Callable[[Path], Path],
) -> None:
    """Verify cleanup run from a linked worktree still refuses a parent of the main checkout, one
    that holds no repository and not that worktree, when git cannot list the worktrees: the main
    worktree is read from the worktree's own `.git` file, not from git."""
    main = init_repo(tmp_path / "checkouts" / "project")
    linked = tmp_path / "worktrees" / "feature"
    git(main, "worktree", "add", "--quiet", "-b", "feature", str(linked))
    tracked = _stale(main / "benchmarks" / "keep.py")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "checkouts"))
    monkeypatch.setenv("PATH", "")
    monkeypatch.chdir(linked)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier()

    assert tracked.exists()


@pytest.mark.parametrize("layout", _WORKTREES_IN_ANOTHER_WORKSPACE)
def test_workspace_clean_from_a_worktree_in_another_workspace_refuses_that_workspaces_data(
    layout: str, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup run from a linked worktree inside another workspace, where the known limit
    resolves shared data to that workspace's `.data`, refuses to prune another workspace's data
    and leaves the main worktree's data alone too."""
    main, linked = request.getfixturevalue(layout)
    shared = _stale(main / ".data" / "reviews" / "shared.json")
    host_own = _stale(linked.parent / ".data" / "reviews" / "host-own.json")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    with pytest.raises(SecurityError, match="another workspace"):
        cleanup_data_tier()

    assert (shared.exists(), host_own.exists()) == (True, True)


@pytest.mark.parametrize("layout", _WORKTREES_IN_ANOTHER_WORKSPACE)
def test_workspace_clean_from_a_worktree_in_another_workspace_prunes_an_absolute_data_dir(
    layout: str, request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an absolute `DEVOPS_CLI_DATA_DIR` outside the other workspace is still pruned from
    a linked worktree inside it: only data resolved into that workspace is refused."""
    _, linked = request.getfixturevalue(layout)
    stale = _stale(tmp_path / "elsewhere" / "logs" / "old.log")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.chdir(linked)

    summary = cleanup_data_tier()

    assert (summary.pruned_files, stale.exists()) == (["logs/old.log"], False)


@pytest.mark.parametrize("configured", [None, "{host}/.data"])
@pytest.mark.parametrize("layout", _WORKTREES_IN_ANOTHER_WORKSPACE)
def test_workspace_clean_from_a_worktree_in_another_workspace_refuses_its_symlinked_data(
    layout: str,
    configured: str | None,
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the other workspace's data is refused when its `.data` links to another volume,
    by default and named absolutely: the link's target lies outside that workspace, but the
    data directory it stands for is in it."""
    _, linked = request.getfixturevalue(layout)
    host = linked.parent
    volume = tmp_path / "volume" / "host-data"
    host_own = _stale(volume / "reviews" / "host-own.json")
    (host / ".data").symlink_to(volume, target_is_directory=True)
    if configured is None:
        monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", configured.format(host=host))
    monkeypatch.chdir(linked)

    with pytest.raises(SecurityError, match="another workspace"):
        cleanup_data_tier()

    assert host_own.exists()


@_OUTER_DIRECTORY_LIMIT
@pytest.mark.parametrize("layout", _WORKTREES_IN_ANOTHER_WORKSPACE)
def test_workspace_clean_from_a_worktree_in_another_workspace_prunes_the_shared_data(
    layout: str, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup run from a linked worktree inside another workspace prunes the main
    worktree's data and leaves the other workspace's own `.data` alone; the known limit
    resolves its data to that other workspace, which cleanup refuses instead."""
    main, linked = request.getfixturevalue(layout)
    shared = _stale(main / ".data" / "reviews" / "shared.json")
    host_own = _stale(linked.parent / ".data" / "reviews" / "host-own.json")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    summary = cleanup_data_tier()

    assert (summary.pruned_files, shared.exists(), host_own.exists()) == (
        ["reviews/shared.json"],
        False,
        True,
    )


@pytest.mark.parametrize("configured", ["/", "/opt", "/tmp", "/run", "/srv", "/mnt", "/home"])
def test_workspace_clean_refuses_a_top_level_directory(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, configured: str
) -> None:
    """Verify cleanup refuses the filesystem root and any directory directly under it, whose
    `cache/` or `logs/` belong to the system or other users, not only the listed system
    directories. The run is a dry run, so a regression prunes nothing."""
    main, _ = repo_with_worktree
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", configured)
    monkeypatch.chdir(main)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier(dry_run=True)


def test_workspace_clean_refuses_a_parent_of_the_home_directory(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup refuses a directory holding the home directory, not only the home
    directory itself: its `cache/` holds other users' files."""
    main, _ = repo_with_worktree
    users = tmp_path / "users"
    other_user = _stale(users / "cache" / "other-user" / "f")
    monkeypatch.setenv("HOME", str(users / "me"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(users))
    monkeypatch.chdir(main)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier()

    assert other_user.exists()


def test_workspace_clean_does_not_follow_a_symlinked_data_subdirectory(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a `logs/` in the data directory that links elsewhere is not pruned through: its
    entries are not links themselves, but they resolve outside the data directory."""
    main, linked = repo_with_worktree
    precious = _stale(tmp_path / "elsewhere" / "precious.log")
    (main / ".data").mkdir()
    (main / ".data" / "logs").symlink_to(precious.parent, target_is_directory=True)
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    summary = cleanup_data_tier()

    assert (summary.pruned_files, summary.pruned_dirs, precious.exists()) == ([], [], True)


@pytest.mark.parametrize("layout", ["repo_with_worktree", "nested_worktree"])
def test_workspace_clean_refuses_the_worktree_it_runs_in(
    layout: str, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup refuses a data directory that is the linked worktree it runs in, outside
    the main checkout or nested in it, whose tracked `benchmarks/` are not the tool's to prune."""
    _, worktree = request.getfixturevalue(layout)
    tracked = _stale(worktree / "benchmarks" / "keep.py")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(worktree))
    monkeypatch.chdir(worktree)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier()

    assert tracked.exists()


def test_workspace_clean_names_the_directory_it_prunes(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops workspace clean` reports the configured data directory it prunes, not a
    `.data/` it no longer necessarily touches, and refuses an unsafe one with an error."""
    main, linked = repo_with_worktree
    _stale(main / "shared-data" / "logs" / "old.log")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "shared-data")
    monkeypatch.chdir(linked)
    runner = CliRunner()

    cleaned = runner.invoke(workspace_app, ["clean"])
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "..")
    refused = runner.invoke(workspace_app, ["clean"])

    assert (
        cleaned.exit_code,
        str((main / "shared-data").resolve()) in " ".join(cleaned.output.split()),
        ".data/" in cleaned.output,
        refused.exit_code,
        "traversal" in refused.output,
    ) == (0, True, False, 1, True)


def test_a_relative_data_dir_override_keeps_one_hallucination_catalog(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a relative `DEVOPS_CLI_DATA_DIR` places the catalog under the main worktree from
    either worktree, as the review, sample and run directories already do."""
    main, linked = repo_with_worktree
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "shared-data")

    catalogs = []
    for start in (main, linked):
        monkeypatch.chdir(start)
        catalogs.append(get_common_hallucinations_file_path())

    assert catalogs == [(main / "shared-data" / CONST_HALLUCINATIONS_FILE_NAME).resolve()] * 2


@pytest.mark.parametrize("start", ["main", "linked"])
def test_the_benchmark_suite_reads_the_shared_feedback_dataset(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, start: str
) -> None:
    """Verify the suite loads the main worktree's dataset from either worktree, both by default
    and by a relative `--dataset`, instead of silently falling back to the baseline cases."""
    main, linked = repo_with_worktree
    _write_dataset(
        main / ".data" / "feedback_dataset.jsonl",
        [{"title": "Recorded finding", "status": "VERIFIED", "persona": "devsecops"}],
    )
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(main if start == "main" else linked)

    titles = (
        [case.title for case in load_feedback_benchmark_dataset()],
        [
            case.title
            for case in load_feedback_benchmark_dataset(Path(".data/feedback_dataset.jsonl"))
        ],
    )

    assert titles == (["Recorded finding"], ["Recorded finding"])


def test_the_benchmark_suite_accepts_a_dataset_in_the_worktree_it_runs_in(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an absolute `--dataset` inside the outside worktree is accepted from a subdirectory
    of it, where it is neither under the main worktree nor under the working directory.

    The temporary directory is an allowed root too, and `tmp_path` lies in it, so it is moved
    elsewhere for the worktree to be the only root that admits the dataset.
    """
    _, linked = repo_with_worktree
    dataset = linked / "worktree-dataset.jsonl"
    _write_dataset(dataset, [{"title": "Worktree finding", "status": "VERIFIED"}])
    (linked / "src").mkdir()
    (tmp_path / "elsewhere-tmp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "elsewhere-tmp"))
    monkeypatch.chdir(linked / "src")

    titles = [case.title for case in load_feedback_benchmark_dataset(dataset)]

    assert titles == ["Worktree finding"]


@pytest.mark.parametrize("layout", ["repo_with_worktree", "nested_worktree"])
@pytest.mark.parametrize(
    ("start", "caught"), [("worktree", 1), ("worktree package", 1), ("main", 0)]
)
def test_prompt_evaluation_reads_shared_data_and_the_current_worktrees_sources(
    layout: str,
    start: str,
    caught: int,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the recorded verdicts come from the main worktree's dataset while the sources they
    cite are read from the worktree the command runs in.

    The linked worktree fixed the file the finding claims does not parse, so run there the
    finding is invalidated; the main checkout still holds the broken version, so run there the
    finding stands. Run from a package with its own `pyproject.toml`, the cited path is still
    read from the worktree root: the working directory holds no `parser.py`, and a verifier
    looking there would stop at the package rather than climb to it.
    """
    main, worktree = request.getfixturevalue(layout)
    _write_dataset(
        main / ".data" / "feedback_dataset.jsonl",
        [
            {
                "title": "Syntax error in parser",
                "status": "INVALIDATED",
                "location": "parser.py:1",
                "description": "",
                "severity": "HIGH",
                "persona": "devsecops",
            }
        ],
    )
    (main / "parser.py").write_text("def parse(:\n", encoding="utf-8")
    (worktree / "parser.py").write_text("def parse() -> int:\n    return 1\n", encoding="utf-8")
    package = worktree / "package"
    package.mkdir()
    (package / "pyproject.toml").write_text("[project]\nname = 'package'\n", encoding="utf-8")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir({"worktree": worktree, "worktree package": package, "main": main}[start])

    result = evaluate_persona_prompts("devsecops")

    assert (result.total_cases, result.caught_invalidations) == (1, caught)


@pytest.mark.parametrize("start", ["main", "linked"])
@pytest.mark.parametrize(
    ("output_dir", "expected"),
    [(None, Path(".data/models")), (Path("bundles"), Path("bundles"))],
)
def test_model_bundles_land_in_the_main_worktree(
    repo_with_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path | None,
    expected: Path,
    start: str,
) -> None:
    """Verify the default bundle directory and a relative `--output` are data paths under the
    main worktree from either worktree, so `--output bundles` means what
    `data.models_dir: bundles` means."""
    main, linked = repo_with_worktree
    workdir = (main if start == "main" else linked) / "src"
    workdir.mkdir()
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(workdir)

    _, manifest = bundle_ollama_models(models=["qwen2.5-coder:7b"], output_dir=output_dir)

    assert manifest == (main / expected).resolve() / "manifest.json"


def test_bundle_models_help_says_a_relative_output_is_under_the_main_worktree() -> None:
    """Verify `devops ai bundle-models --help` tells the user a relative `--output` is a data
    path under the main worktree, not a path under the working directory."""
    result = CliRunner().invoke(ai_app, ["bundle-models", "--help"], terminal_width=200)

    assert (result.exit_code, "under the main worktree" in " ".join(result.output.split())) == (
        0,
        True,
    )


@pytest.mark.parametrize(
    ("layout", "start"),
    [
        ("repo_with_worktree", "main"),
        ("repo_with_worktree", "linked"),
        *((layout, "main") for layout in _WORKTREES_IN_ANOTHER_WORKSPACE),
        *(
            pytest.param(layout, "linked", marks=_OUTER_DIRECTORY_LIMIT)
            for layout in _WORKTREES_IN_ANOTHER_WORKSPACE
        ),
    ],
)
def test_workspace_discovery_lists_the_main_checkouts_repositories(
    layout: str, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, start: str
) -> None:
    """Verify the workspaces endpoint served from either worktree, outside the main checkout or
    inside another workspace, scans the main checkout's `repos/`, which is gitignored and so
    exists only there."""
    main, linked = request.getfixturevalue(layout)
    (main / "repos" / "owner" / "tool" / ".git").mkdir(parents=True)
    monkeypatch.chdir(main if start == "main" else linked)

    response = asyncio.run(list_workspaces())

    assert (response.workspace_root, [repo.name for repo in response.repositories]) == (
        str(main.resolve()),
        ["owner/tool"],
    )


@pytest.mark.parametrize(
    "layout",
    [
        "repo_with_worktree",
        *(
            pytest.param(layout, marks=_OUTER_DIRECTORY_LIMIT)
            for layout in _WORKTREES_IN_ANOTHER_WORKSPACE
        ),
    ],
)
def test_an_analysis_saved_in_a_worktree_is_found_from_the_main_one(
    layout: str, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify analysis metadata saved from a linked worktree, outside the main checkout or inside
    another workspace, is cached in the main worktree's data directory."""
    main, linked = request.getfixturevalue(layout)
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)

    saved = save_analysis_metadata("branch", "feature", "Feature analysis", [], repo_root=linked)
    loaded = load_cached_analysis(main)

    assert (saved.parent, loaded.project.title if loaded else None) == (
        (main / ".data" / "analysis").resolve(),
        "Feature analysis",
    )


@pytest.mark.parametrize("configured", [".git", "{bare}", ".git/worktrees/feature"])
def test_workspace_clean_refuses_a_git_directory(
    repo_with_worktree: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
    git: Callable[..., None],
) -> None:
    """Verify cleanup refuses a git directory, whose `logs/` are the repository's reflogs: the
    main worktree's `.git`, a bare repository, or a linked worktree's directory inside `.git`."""
    main, linked = repo_with_worktree
    bare = tmp_path / "bare.git"
    git(main, "clone", "--quiet", "--bare", str(main), str(bare))
    reflogs = (_stale(main / ".git" / "logs" / "HEAD"), _stale(bare / "logs" / "HEAD"))
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", configured.format(bare=bare))
    monkeypatch.chdir(linked)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier()

    assert [path.exists() for path in reflogs] == [True, True]


@pytest.mark.parametrize("start", ["main", "linked"])
def test_workspace_clean_refuses_a_data_directory_holding_tracked_files(
    repo_with_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    start: str,
    git: Callable[..., None],
) -> None:
    """Verify cleanup refuses a data directory that is an ordinary directory of the checkout, whose
    committed `cache/` sources are not the tool's to prune."""
    main, linked = repo_with_worktree
    tracked = _stale(main / "src" / "pkg" / "cache" / "tracked.py")
    git(main, "add", ".")
    git(main, "commit", "--quiet", "-m", "sources")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "src/pkg")
    monkeypatch.chdir(main if start == "main" else linked)

    with pytest.raises(SecurityError, match="tracked"):
        cleanup_data_tier()

    assert tracked.exists()


def test_workspace_clean_refuses_a_data_directory_holding_another_repository(
    repo_with_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    init_repo: Callable[[Path], Path],
) -> None:
    """Verify cleanup refuses a data directory with a repository in a directory it prunes, such as
    a clone at `repos/cache`, which the checkout's own index does not list."""
    main, _ = repo_with_worktree
    clone = init_repo(main / "repos" / "cache")
    kept = _stale(clone / "logs" / "kept.log")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "repos")
    monkeypatch.chdir(main)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier()

    assert kept.exists()


def test_workspace_clean_refuses_a_checkout_it_cannot_ask_git_about(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup refuses a data directory inside a checkout when git cannot say whether it
    holds tracked files, rather than pruning it unchecked."""
    main, linked = repo_with_worktree
    kept = _stale(main / ".data" / "logs" / "old.log")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.chdir(linked)

    with pytest.raises(SecurityError, match="tracked"):
        cleanup_data_tier()

    assert kept.exists()


def test_workspace_clean_refuses_the_parent_of_the_worktree_it_runs_in_without_git(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cleanup run from a linked worktree refuses the directory holding that worktree when
    git cannot list the worktrees: the worktree it runs in is known without git."""
    _, linked = repo_with_worktree
    tracked = _stale(linked / "benchmarks" / "keep.py")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "worktrees"))
    monkeypatch.setenv("PATH", "")
    monkeypatch.chdir(linked)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier()

    assert tracked.exists()


def test_workspace_clean_in_a_clone_under_repos_prunes_the_workspace_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, init_repo: Callable[[Path], Path]
) -> None:
    """Verify cleanup, reviews and the analysis cache of a repository cloned under the workspace's
    `repos/` all use the workspace's data directory, where its reviews are written, and cleanup
    leaves a `.data` of the clone's own alone."""
    workspace = init_repo(tmp_path / "workspace")
    clone = init_repo(workspace / "repos" / "owner" / "tool")
    shared = _stale(workspace / ".data" / "reviews" / "old.json")
    clone_own = _stale(clone / ".data" / "logs" / "clone.log")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(clone)

    summary = cleanup_data_tier()

    assert (
        summary.pruned_files,
        shared.exists(),
        clone_own.exists(),
        _get_reviews_base_dir(),
        analysis_directory(clone),
    ) == (
        ["reviews/old.json"],
        False,
        True,
        (workspace / ".data" / "reviews").resolve(),
        (workspace / ".data" / "analysis").resolve(),
    )


@_OUTER_DIRECTORY_LIMIT
def test_a_project_in_a_home_directory_kept_in_git_keeps_its_own_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, init_repo: Callable[[Path], Path]
) -> None:
    """Verify cleanup, reviews and the analysis cache of a project under a home directory kept in
    git use the project's own data directory and leave the home directory's `.data` alone; the
    known limit resolves them to the home directory, as it does a `repos/` clone's to its
    workspace, and cleanup cannot tell the two apart."""
    home = init_repo(tmp_path / "home")
    monkeypatch.setenv("HOME", str(home))
    project = init_repo(home / "code" / "project")
    own = _stale(project / ".data" / "reviews" / "old.json")
    home_own = _stale(home / ".data" / "logs" / "home.log")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(project)

    summary = cleanup_data_tier()

    assert (
        summary.pruned_files,
        own.exists(),
        home_own.exists(),
        _get_reviews_base_dir(),
        analysis_directory(project),
    ) == (
        ["reviews/old.json"],
        False,
        True,
        (project / ".data" / "reviews").resolve(),
        (project / ".data" / "analysis").resolve(),
    )


def test_workspace_clean_dry_run_names_and_checks_what_it_would_prune(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops workspace clean --dry-run` names the data directory and the entries it would
    prune, keeping them, and refuses a data directory the real run refuses."""
    main, linked = repo_with_worktree
    stale = _stale(main / "shared-data" / "logs" / "old.log")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "shared-data")
    monkeypatch.chdir(linked)
    runner = CliRunner()

    planned = runner.invoke(workspace_app, ["clean", "--dry-run"])
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", ".git")
    refused = runner.invoke(workspace_app, ["clean", "--dry-run"])
    output = "".join(planned.output.split())

    assert (
        planned.exit_code,
        str((main / "shared-data").resolve()) in output,
        "logs/old.log" in output,
        stale.exists(),
        refused.exit_code,
        "notadedicateddatadirectory" in "".join(refused.output.split()),
    ) == (0, True, True, True, 1, True)


def test_the_library_drift_report_is_saved_in_the_shared_analysis_directory(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ai audit-library-usage` run from a linked worktree saves its report in the
    shared analysis directory, which outlives the worktree, not in the worktree's own `.data`."""
    from devops_cli.ai.library.drift_auditor import LibraryDriftAuditor

    main, linked = repo_with_worktree
    saved: list[Path] = []

    def audit(self: Any, ws_dir: Path, package_filter: str | None, save_report_path: Path) -> Any:
        saved.append(save_report_path)
        raise RuntimeError("stop after resolving the report path")

    monkeypatch.setattr(LibraryDriftAuditor, "audit_workspace", audit)
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(linked)

    CliRunner().invoke(ai_app, ["audit-library-usage"])

    assert saved == [(main / ".data" / "analysis").resolve() / "api_drift_report.json"]


@pytest.mark.parametrize(
    "command", [["prompt-eval", "--help"], ["benchmark", "--help"]], ids=["ai", "benchmark"]
)
def test_dataset_help_says_a_relative_dataset_is_under_the_main_worktree(
    command: list[str],
) -> None:
    """Verify the `--dataset` help of `devops ai prompt-eval` and the benchmark suite tells the
    user a relative path is a data path under the main worktree."""
    result = CliRunner().invoke(ai_app, command, terminal_width=200)

    assert (result.exit_code, "under the main worktree" in " ".join(result.output.split())) == (
        0,
        True,
    )


def _age_tree(root: Path) -> None:
    """Every entry under `root`, and `root` itself, last written a fortnight ago."""
    for top, dirs, files in os.walk(root):
        for name in (*dirs, *files):
            os.utime(Path(top) / name, (_A_FORTNIGHT_AGO, _A_FORTNIGHT_AGO))
    os.utime(root, (_A_FORTNIGHT_AGO, _A_FORTNIGHT_AGO))


@pytest.mark.parametrize("bare", ["cache/mirror.git", "cache"])
def test_workspace_clean_refuses_a_data_directory_holding_a_bare_repository(
    repo_with_worktree: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bare: str,
    git: Callable[..., None],
) -> None:
    """Verify cleanup refuses a data directory with a bare repository in a directory it prunes, or
    that is one, which has no `.git` entry to find: a mirror kept at `cache/mirror.git`, or a bare
    clone made at `cache` itself."""
    main, _ = repo_with_worktree
    data = tmp_path / "data"
    mirror = data / bare
    mirror.parent.mkdir(parents=True, exist_ok=True)
    git(main, "clone", "--quiet", "--bare", str(main), str(mirror))
    _age_tree(data)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data))
    monkeypatch.chdir(main)

    with pytest.raises(SecurityError, match="not a dedicated data directory"):
        cleanup_data_tier(dry_run=True)

    assert [(mirror / name).exists() for name in ("HEAD", "objects", "refs")] == [True] * 3


def test_workspace_clean_in_a_submodule_prunes_the_superprojects_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    git: Callable[..., None],
    init_repo: Callable[[Path], Path],
) -> None:
    """Verify cleanup, reviews and the analysis cache of a submodule use the superproject's data
    directory, as a clone under `repos/` uses the workspace's, and cleanup leaves a `.data` of
    the submodule's own alone."""
    library = init_repo(tmp_path / "library")
    superproject = init_repo(tmp_path / "superproject")
    git(
        superproject,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "--quiet",
        str(library),
        "vendor/library",
    )
    submodule = superproject / "vendor" / "library"
    shared = _stale(superproject / ".data" / "reviews" / "old.json")
    submodule_own = _stale(submodule / ".data" / "logs" / "submodule.log")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(submodule)

    summary = cleanup_data_tier()

    assert (
        main_worktree_root(submodule),
        summary.pruned_files,
        shared.exists(),
        submodule_own.exists(),
        _get_reviews_base_dir(),
        analysis_directory(submodule),
    ) == (
        superproject.resolve(),
        ["reviews/old.json"],
        False,
        True,
        (superproject / ".data" / "reviews").resolve(),
        (superproject / ".data" / "analysis").resolve(),
    )


def test_a_worktree_of_a_bare_repository_keeps_its_own_data_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    git: Callable[..., None],
    init_repo: Callable[[Path], Path],
) -> None:
    """Verify a linked worktree of a bare repository, which has no main worktree, resolves data
    paths under itself rather than inside the bare git directory, and cleanup prunes it there."""
    source = init_repo(tmp_path / "source")
    bare = tmp_path / "repo.git"
    git(source, "clone", "--quiet", "--bare", str(source), str(bare))
    worktree = tmp_path / "feature"
    git(bare, "worktree", "add", "--quiet", "-b", "feature", str(worktree))
    own = _stale(worktree / ".data" / "reviews" / "old.json")
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(worktree)

    summary = cleanup_data_tier()

    assert (
        main_worktree_root(worktree),
        summary.pruned_files,
        own.exists(),
        _get_reviews_base_dir(),
        (bare / ".data").exists(),
    ) == (
        worktree.resolve(),
        ["reviews/old.json"],
        False,
        (worktree / ".data" / "reviews").resolve(),
        False,
    )


@pytest.mark.parametrize("configured", [None, "shared-data"])
def test_dashboard_controller_and_sandbox_data_is_shared_from_an_outside_worktree(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, configured: str | None
) -> None:
    """Verify the dashboard's review list, the controller's checkpoints and the sandbox registry
    and incidents use the main worktree's data directory from a linked worktree outside it, by
    default and with a relative `DEVOPS_CLI_DATA_DIR`, not a `.data` lost with the worktree."""
    from devops_cli.ai.controller.manager import ConstellationManager
    from devops_cli.sandbox.logs import resolve_incident_dir
    from devops_cli.sandbox.registry import get_default_sandbox_registry_path
    from devops_cli.ui.data_providers import _reviews_root

    main, linked = repo_with_worktree
    data = main / (configured or ".data")
    (data / "reviews").mkdir(parents=True)
    if configured is None:
        monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", configured)
    monkeypatch.chdir(linked)

    resolved = (
        _reviews_root(),
        ConstellationManager().data_dir,
        get_default_sandbox_registry_path(),
        resolve_incident_dir(),
    )

    data = data.resolve()
    assert resolved == (
        data / "reviews",
        data,
        data / "sandbox" / "instances.json",
        data / "sandbox" / "incidents",
    )


@pytest.mark.parametrize("start", ["main", "linked"])
def test_the_ci_cache_is_kept_in_the_shared_cache_directory_per_worktree(
    repo_with_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, start: str
) -> None:
    """Verify the CI gate's cache lands in the shared data directory's `cache/`, which cleanup
    prunes, from a subdirectory of any worktree rather than a `.data` under the working
    directory, and that each worktree keeps its own entry there: a gate never trusts a result
    recorded for another worktree's files."""
    from devops_cli.ci.cache import CICachedCheck, get_ci_cache, save_ci_cache

    main, linked = repo_with_worktree
    root = main if start == "main" else linked
    other = linked if start == "main" else main
    (root / "sub").mkdir()
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
    monkeypatch.chdir(root / "sub")
    check = CICachedCheck(name="t", display_title="T", passed=True, duration_seconds=1.0)

    save_ci_cache("fp", "sha", [check], {}, root=root)
    cached = sorted((main / ".data" / "cache").glob("ci_cache*.json"))

    assert (
        len(cached),
        get_ci_cache("fp", root=root) is not None,
        get_ci_cache("fp", root=other) is None,
        (root / "sub" / ".data").exists(),
    ) == (1, True, True, False)
