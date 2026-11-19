"""Tests for devops repos sync and clone integration with Gitea (#1090)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.config.settings import load_settings, save_settings
from devops_cli.http.entry import install_transport, remove_transport
from tests.support.fakes.git import GitFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer


@pytest.fixture(autouse=True)
def cleanup_transport() -> Any:
    yield
    remove_transport()


def _setup_config(
    keyring_store: FakeKeyring,
    url: str = "https://git.example.com",
    username: str = "alice",
    branches: tuple[str, ...] = ("main",),
) -> None:
    keyring_store.set_password("devops-cli", "gitea_token", "test-token")
    settings = load_settings()
    settings.gitea.url = url
    settings.gitea.username = username
    settings.gitea.github_branches = branches
    save_settings(settings, keys=("gitea.url", "gitea.username", "gitea.github_branches"))


def test_repos_sync_fetches_both_remotes_and_pushes_default_branch(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """repos sync fetches origin and gitea, then pushes main to Gitea."""
    _setup_config(keyring_store)

    repos_dir = tmp_path / "repos"
    clone_dir = repos_dir / "myorg" / "myrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    # Remotes: origin and gitea
    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote"],
        ProcessAnswer(stdout="origin\ngitea\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "origin"], ProcessAnswer())
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "gitea"], ProcessAnswer())
    git_fake.answer(
        ["git", "-C", str(clone_dir), "branch", "--show-current"], ProcessAnswer(stdout="main\n")
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "pull", "origin", "main"], ProcessAnswer())

    # Gitea sync steps
    git_fake.answer(
        ["git", "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "for-each-ref",
            "--format=%(refname:strip=3)",
            "refs/remotes/origin",
        ],
        ProcessAnswer(stdout="HEAD\nmain\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "push",
            "--porcelain",
            "gitea",
            "refs/remotes/origin/main:refs/heads/main",
        ],
        ProcessAnswer(stdout="*\trefs/remotes/origin/main:refs/heads/main\t[new branch]\n"),
    )

    result = cli("repos", "sync", "--base-dir", str(repos_dir))
    assert result.exit_code == 0
    assert "main updated" in result.output
    calls = [call.argv for call in git_fake.calls]
    assert any("fetch" in call and "origin" in call for call in calls)
    assert any("fetch" in call and "gitea" in call for call in calls)
    assert any("push" in call and "--porcelain" in call for call in calls)


def test_repos_sync_no_gitea_flag_skips_push(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """repos sync --no-gitea fetches remotes but skips Gitea push."""
    _setup_config(keyring_store)

    repos_dir = tmp_path / "repos"
    clone_dir = repos_dir / "myorg" / "myrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote"],
        ProcessAnswer(stdout="origin\ngitea\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "origin"], ProcessAnswer())
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "gitea"], ProcessAnswer())
    git_fake.answer(
        ["git", "-C", str(clone_dir), "branch", "--show-current"], ProcessAnswer(stdout="main\n")
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "pull", "origin", "main"], ProcessAnswer())

    result = cli("repos", "sync", "--no-gitea", "--base-dir", str(repos_dir))
    assert result.exit_code == 0
    calls = [call.argv for call in git_fake.calls]
    assert not any("push" in call for call in calls)


def test_repos_sync_matches_branch_patterns_and_ignores_iteration_branches(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """sync pushes default branch and matching release/* patterns, ignoring iteration branch and nested release/1/fix."""
    _setup_config(keyring_store, branches=("main", "release/*"))

    repos_dir = tmp_path / "repos"
    clone_dir = repos_dir / "myorg" / "myrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote"],
        ProcessAnswer(stdout="origin\ngitea\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "origin"], ProcessAnswer())
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "gitea"], ProcessAnswer())
    git_fake.answer(
        ["git", "-C", str(clone_dir), "branch", "--show-current"], ProcessAnswer(stdout="main\n")
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "pull", "origin", "main"], ProcessAnswer())

    git_fake.answer(
        ["git", "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    # Origin holds main, release/1.0, release/1/fix (nested, does not match), and topic/feat (iteration branch)
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "for-each-ref",
            "--format=%(refname:strip=3)",
            "refs/remotes/origin",
        ],
        ProcessAnswer(stdout="HEAD\nmain\nrelease/1.0\nrelease/1/fix\ntopic/feat\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "push",
            "--porcelain",
            "gitea",
            "refs/remotes/origin/main:refs/heads/main",
            "refs/remotes/origin/release/1.0:refs/heads/release/1.0",
        ],
        ProcessAnswer(
            stdout="*\trefs/remotes/origin/main:refs/heads/main\t[new branch]\n"
            "*\trefs/remotes/origin/release/1.0:refs/heads/release/1.0\t[new branch]\n"
        ),
    )

    result = cli("repos", "sync", "--base-dir", str(repos_dir))
    assert result.exit_code == 0
    assert "main updated" in result.output
    assert "release/1.0 updated" in result.output
    calls = [call.argv for call in git_fake.calls]
    push_calls = [call for call in calls if "push" in call]
    assert len(push_calls) == 1
    # Check that release/1/fix and topic/feat are not in refspecs
    refspecs = push_calls[0]
    assert not any("release/1/fix" in arg for arg in refspecs)
    assert not any("topic/feat" in arg for arg in refspecs)


def test_repos_sync_reports_rejected_branch_with_inspect_command(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """sync reports non-fast-forward rejected branch with git log command and exits 1."""
    _setup_config(keyring_store)

    repos_dir = tmp_path / "repos"
    clone_dir = repos_dir / "myorg" / "myrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote"],
        ProcessAnswer(stdout="origin\ngitea\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "origin"], ProcessAnswer())
    git_fake.answer(["git", "-C", str(clone_dir), "fetch", "--prune", "gitea"], ProcessAnswer())
    git_fake.answer(
        ["git", "-C", str(clone_dir), "branch", "--show-current"], ProcessAnswer(stdout="main\n")
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(["git", "-C", str(clone_dir), "pull", "origin", "main"], ProcessAnswer())

    git_fake.answer(
        ["git", "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "for-each-ref",
            "--format=%(refname:strip=3)",
            "refs/remotes/origin",
        ],
        ProcessAnswer(stdout="HEAD\nmain\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "push",
            "--porcelain",
            "gitea",
            "refs/remotes/origin/main:refs/heads/main",
        ],
        ProcessAnswer(
            stdout="!\trefs/remotes/origin/main:refs/heads/main\t[rejected] (non-fast-forward)\n",
            returncode=1,
        ),
    )

    result = cli("repos", "sync", "--base-dir", str(repos_dir))
    assert result.exit_code == 1
    assert "rejected (non-fast-forward)" in result.output
    assert "git log gitea/main ^origin/main" in result.output


def test_repos_sync_skips_push_after_failed_fetch(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """When fetch fails, sync reports the error and makes no Gitea push for that clone."""
    _setup_config(keyring_store)

    repos_dir = tmp_path / "repos"
    clone_dir = repos_dir / "myorg" / "myrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote"],
        ProcessAnswer(stdout="origin\ngitea\n"),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "fetch", "--prune", "origin"],
        ProcessAnswer(returncode=128, stderr="fatal: remote error"),
    )

    result = cli("repos", "sync", "--base-dir", str(repos_dir))
    assert result.exit_code == 1
    calls = [call.argv for call in git_fake.calls]
    assert not any("push" in call for call in calls)


def test_repos_clone_runs_gitea_ensure_step(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
    known_hosts: Path,
) -> None:
    """repos clone ensures Gitea org, repo, protections, and remote URL when gitea.url is set."""
    _setup_config(keyring_store)

    repos_dir = tmp_path / "repos"
    dest_dir = repos_dir / "myorg" / "newrepo"

    gitea_calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        gitea_calls.append(f"{request.method} {url_str}")
        if "/api/v1/user" in url_str and request.method == "GET":
            return httpx2.Response(200, json={"id": 1, "login": "alice", "username": "alice"})
        if "/api/v1/orgs/myorg" in url_str and request.method == "GET":
            return httpx2.Response(200, json={"id": 10, "name": "myorg"})
        if "/api/v1/repos/myorg/newrepo" in url_str and request.method == "GET":
            return httpx2.Response(404, json={"message": "Not found"})
        if "/api/v1/orgs/myorg/repos" in url_str and request.method == "POST":
            return httpx2.Response(
                201, json={"id": 100, "name": "newrepo", "private": True, "default_branch": "main"}
            )
        if "/branch_protections" in url_str and request.method == "GET":
            return httpx2.Response(200, json=[])
        if "/branch_protections" in url_str and request.method == "POST":
            return httpx2.Response(
                201, json={"rule_name": "main", "enable_push": True, "enable_force_push": False}
            )
        return httpx2.Response(200)

    install_transport(lambda level: httpx2.MockTransport(handler))

    # Clone git commands
    git_fake.answer(
        ["git", "clone", "--", "https://github.com/myorg/newrepo.git", str(dest_dir)],
        ProcessAnswer(),
    )
    # Ensure clone remotes git commands
    git_fake.answer(
        ["git", "-C", str(dest_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        ["git", "-C", str(dest_dir), "remote", "-v"],
        ProcessAnswer(stdout="origin https://github.com/myorg/newrepo.git (fetch)\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(dest_dir),
            "remote",
            "add",
            "gitea",
            "https://git.example.com/myorg/newrepo.git",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(dest_dir),
            "config",
            "--add",
            "credential.https://git.example.com.helper",
            "",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(dest_dir),
            "config",
            "--add",
            "credential.https://git.example.com.helper",
            "!devops repos gitea credential",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(dest_dir), "config", "checkout.defaultRemote", "origin"],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(dest_dir), "config", "remote.gitea.tagOpt", "--no-tags"],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(dest_dir), "push", "gitea", "refs/remotes/origin/main:refs/heads/main"],
        ProcessAnswer(),
    )

    result = cli(
        "repos", "clone", "https://github.com/myorg/newrepo.git", "--base-dir", str(repos_dir)
    )
    assert result.exit_code == 0
    assert any("/api/v1/orgs/myorg/repos" in call for call in gitea_calls)


def test_repos_clone_gitea_failure_warns_and_keeps_clone(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
    known_hosts: Path,
) -> None:
    """When Gitea ensure step fails with GiteaError, clone warns and keeps the clone."""
    _setup_config(keyring_store)

    repos_dir = tmp_path / "repos"
    dest_dir = repos_dir / "myorg" / "failrepo"

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        if "/api/v1/user" in url_str:
            return httpx2.Response(200, json={"id": 1, "login": "alice", "username": "alice"})
        # 500 error on org
        return httpx2.Response(500, json={"message": "Internal Gitea failure"})

    install_transport(lambda level: httpx2.MockTransport(handler))

    git_fake.answer(
        ["git", "clone", "--", "https://github.com/myorg/failrepo.git", str(dest_dir)],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(dest_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )

    result = cli(
        "repos", "clone", "https://github.com/myorg/failrepo.git", "--base-dir", str(repos_dir)
    )
    assert result.exit_code == 0
    assert "Gitea remote setup for failrepo failed" in result.output
