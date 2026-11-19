"""Tests for devops repos remotes command (#1090)."""

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
    keyring_store: FakeKeyring, url: str = "https://git.example.com", username: str = "alice"
) -> None:
    keyring_store.set_password("devops-cli", "gitea_token", "test-token")
    settings = load_settings()
    settings.gitea.url = url
    settings.gitea.username = username
    save_settings(settings, keys=("gitea.url", "gitea.username"))


def test_remotes_exits_when_gitea_url_unset(
    cli: Callable[..., Any], isolate_devops_cli_config: Path
) -> None:
    """remotes exits 1 and names 'devops repos gitea connect' when gitea.url is not configured."""
    result = cli("repos", "remotes")
    assert result.exit_code != 0
    assert "devops repos gitea connect" in result.output


def test_remotes_dry_run_makes_only_get_calls(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """remotes --dry-run makes only GET requests and runs no push."""
    _setup_config(keyring_store)

    clone_dir = tmp_path / "repos" / "testorg" / "testrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    requests_made: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests_made.append(request)
        url_str = str(request.url)
        if "/api/v1/user" in url_str:
            return httpx2.Response(200, json={"id": 1, "login": "alice", "username": "alice"})
        if "/api/v1/orgs/testorg" in url_str:
            return httpx2.Response(200, json={"id": 10, "name": "testorg"})
        if "/api/v1/repos/testorg/testrepo/branch_protections" in url_str:
            return httpx2.Response(200, json=[])
        if "/api/v1/repos/testorg/testrepo" in url_str:
            return httpx2.Response(
                200, json={"id": 100, "name": "testrepo", "private": True, "default_branch": "main"}
            )
        return httpx2.Response(404)

    install_transport(lambda level: httpx2.MockTransport(handler))

    git_fake.answer(
        ["git", "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote", "-v"],
        ProcessAnswer(stdout="origin https://github.com/testorg/testrepo.git (fetch)\n"),
    )

    result = cli("repos", "remotes", "--base-dir", str(tmp_path / "repos"), "--dry-run")
    assert result.exit_code == 0
    assert all(r.method == "GET" for r in requests_made)
    # Ensure no git push was called
    assert not any("push" in call.argv for call in git_fake.calls)


def test_remotes_creates_and_seeds(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """remotes creates missing repo, adds branch protection, sets remote and seeds main."""
    _setup_config(keyring_store)

    clone_dir = tmp_path / "repos" / "myorg" / "myrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    post_calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        if request.method == "POST":
            post_calls.append(url_str)
        if "/branch_protections" in url_str and request.method == "GET":
            return httpx2.Response(200, json=[])
        if "/branch_protections" in url_str and request.method == "POST":
            return httpx2.Response(
                201, json={"rule_name": "main", "enable_push": True, "enable_force_push": False}
            )
        if "/api/v1/user" in url_str and request.method == "GET":
            return httpx2.Response(200, json={"id": 1, "login": "alice", "username": "alice"})
        if "/api/v1/orgs/myorg/repos" in url_str and request.method == "POST":
            return httpx2.Response(
                201, json={"id": 100, "name": "myrepo", "private": True, "default_branch": "main"}
            )
        if "/api/v1/orgs/myorg" in url_str and request.method == "GET":
            return httpx2.Response(404, json={"message": "Not found"})
        if "/api/v1/orgs" in url_str and request.method == "POST":
            return httpx2.Response(201, json={"id": 10, "name": "myorg", "visibility": "private"})
        if "/api/v1/repos/myorg/myrepo" in url_str and request.method == "GET":
            return httpx2.Response(404, json={"message": "Not found"})
        return httpx2.Response(200)

    install_transport(lambda level: httpx2.MockTransport(handler))

    git_fake.answer(
        ["git", "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote", "-v"],
        ProcessAnswer(stdout="origin https://github.com/myorg/myrepo.git (fetch)\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "remote",
            "add",
            "gitea",
            "https://git.example.com/myorg/myrepo.git",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
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
            str(clone_dir),
            "config",
            "--add",
            "credential.https://git.example.com.helper",
            "!devops repos gitea credential",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "checkout.defaultRemote", "origin"], ProcessAnswer()
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "remote.gitea.tagOpt", "--no-tags"], ProcessAnswer()
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "push", "gitea", "refs/remotes/origin/main:refs/heads/main"],
        ProcessAnswer(stdout="* [new branch] origin/main -> main\n"),
    )

    result = cli("repos", "remotes", "--base-dir", str(tmp_path / "repos"))
    assert result.exit_code == 0
    assert any("/api/v1/orgs" in call for call in post_calls)
    assert any("/api/v1/orgs/myorg/repos" in call for call in post_calls)
    assert any("/branch_protections" in call for call in post_calls)
    assert any("push" in call.argv for call in git_fake.calls)


def test_remotes_user_namespace_when_owner_matches_login(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """remotes creates under user namespace when owner equals login and makes no org calls."""
    _setup_config(keyring_store, username="alice")

    clone_dir = tmp_path / "repos" / "alice" / "userrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    post_calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        if request.method == "POST":
            post_calls.append(url_str)
        if "/branch_protections" in url_str and request.method == "GET":
            return httpx2.Response(200, json=[])
        if "/branch_protections" in url_str and request.method == "POST":
            return httpx2.Response(
                201, json={"rule_name": "main", "enable_push": True, "enable_force_push": False}
            )
        if "/api/v1/user/repos" in url_str and request.method == "POST":
            return httpx2.Response(
                201, json={"id": 100, "name": "userrepo", "private": True, "default_branch": "main"}
            )
        if "/api/v1/user" in url_str and request.method == "GET":
            return httpx2.Response(200, json={"id": 1, "login": "alice", "username": "alice"})
        if "/api/v1/repos/alice/userrepo" in url_str and request.method == "GET":
            return httpx2.Response(404, json={"message": "Not found"})
        return httpx2.Response(200)

    install_transport(lambda level: httpx2.MockTransport(handler))

    git_fake.answer(
        ["git", "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote", "-v"],
        ProcessAnswer(stdout="origin https://github.com/alice/userrepo.git (fetch)\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "remote",
            "add",
            "gitea",
            "https://git.example.com/alice/userrepo.git",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
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
            str(clone_dir),
            "config",
            "--add",
            "credential.https://git.example.com.helper",
            "!devops repos gitea credential",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "checkout.defaultRemote", "origin"], ProcessAnswer()
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "remote.gitea.tagOpt", "--no-tags"], ProcessAnswer()
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "push", "gitea", "refs/remotes/origin/main:refs/heads/main"],
        ProcessAnswer(),
    )

    result = cli("repos", "remotes", "--base-dir", str(tmp_path / "repos"))
    assert result.exit_code == 0
    assert any("/api/v1/user/repos" in call for call in post_calls)
    assert not any("/api/v1/orgs" in call for call in post_calls)


def test_remotes_skips_standalone_clones(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """remotes skips repos/_standalone/* clones with a note."""
    _setup_config(keyring_store)

    standalone_dir = tmp_path / "repos" / "_standalone" / "mytool"
    standalone_dir.mkdir(parents=True)
    (standalone_dir / ".git").mkdir()

    result = cli("repos", "remotes", "--base-dir", str(tmp_path / "repos"))
    assert result.exit_code == 0
    assert "standalone" in result.output.lower() or "skip" in result.output.lower()


def test_remotes_adds_path_to_extra_checkouts(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """remotes --path records path once in gitea.extra_checkouts."""
    _setup_config(keyring_store)

    extra_dir = tmp_path / "extra_repo"
    extra_dir.mkdir(parents=True)
    (extra_dir / ".git").mkdir()

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        if "/api/v1/user" in url_str:
            return httpx2.Response(200, json={"id": 1, "login": "alice", "username": "alice"})
        if "/api/v1/orgs/" in url_str and request.method == "GET":
            return httpx2.Response(200, json={"id": 10, "name": "myorg"})
        if "/branch_protections" in url_str and request.method == "GET":
            return httpx2.Response(
                200, json=[{"rule_name": "main", "enable_push": True, "enable_force_push": False}]
            )
        if "/api/v1/repos/" in url_str and request.method == "GET":
            return httpx2.Response(
                200, json={"id": 1, "name": "extra_repo", "private": True, "default_branch": "main"}
            )
        return httpx2.Response(200)

    install_transport(lambda level: httpx2.MockTransport(handler))

    git_fake.answer(
        ["git", "remote", "get-url", "origin"],
        ProcessAnswer(stdout="https://github.com/myorg/extra_repo.git\n"),
    )
    git_fake.answer(
        ["git", "-C", str(extra_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        ["git", "-C", str(extra_dir), "remote", "-v"],
        ProcessAnswer(
            stdout="origin https://github.com/myorg/extra_repo.git (fetch)\ngitea https://git.example.com/myorg/extra_repo.git (fetch)\n"
        ),
    )
    git_fake.answer(
        ["git", "-C", str(extra_dir), "remote", "get-url", "gitea"],
        ProcessAnswer(stdout="https://git.example.com/myorg/extra_repo.git\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(extra_dir),
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
            str(extra_dir),
            "config",
            "--add",
            "credential.https://git.example.com.helper",
            "!devops repos gitea credential",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(extra_dir), "config", "checkout.defaultRemote", "origin"], ProcessAnswer()
    )
    git_fake.answer(
        ["git", "-C", str(extra_dir), "config", "remote.gitea.tagOpt", "--no-tags"], ProcessAnswer()
    )
    git_fake.answer(
        ["git", "-C", str(extra_dir), "push", "gitea", "refs/remotes/origin/main:refs/heads/main"],
        ProcessAnswer(),
    )

    result = cli(
        "repos", "remotes", "--base-dir", str(tmp_path / "repos"), "--path", str(extra_dir)
    )
    assert result.exit_code == 0

    settings = load_settings()
    assert str(extra_dir.resolve()) in settings.gitea.extra_checkouts


def test_remotes_exits_when_token_unset(
    cli: Callable[..., Any], isolate_devops_cli_config: Path, keyring_store: FakeKeyring
) -> None:
    """remotes exits 1 and names 'devops config set gitea.token' when token is unset."""
    settings = load_settings()
    settings.gitea.url = "https://git.example.com"
    save_settings(settings, keys=("gitea.url",))

    result = cli("repos", "remotes")
    assert result.exit_code != 0
    assert "gitea.token" in result.output


def test_remotes_updates_remote_url_when_changed(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """remotes runs 'git remote set-url gitea' when the URL changes."""
    _setup_config(keyring_store)

    clone_dir = tmp_path / "repos" / "testorg" / "testrepo"
    clone_dir.mkdir(parents=True)
    (clone_dir / ".git").mkdir()

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        if "/api/v1/user" in url_str:
            return httpx2.Response(200, json={"id": 1, "login": "testorg", "username": "testorg"})
        if "/branch_protections" in url_str and request.method == "GET":
            return httpx2.Response(200, json=[])
        if "/branch_protections" in url_str and request.method == "POST":
            return httpx2.Response(
                201, json={"rule_name": "main", "enable_push": True, "enable_force_push": False}
            )
        if "/api/v1/repos/testorg/testrepo" in url_str:
            return httpx2.Response(
                200, json={"id": 1, "name": "testrepo", "default_branch": "main"}
            )
        return httpx2.Response(200, json={})

    install_transport(lambda level: httpx2.MockTransport(handler))

    git_fake.answer(
        ["git", "-C", str(clone_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(stdout="origin/main\n"),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote", "-v"],
        ProcessAnswer(
            stdout="origin https://github.com/testorg/testrepo.git (fetch)\ngitea https://old.example.com/testorg/testrepo.git (fetch)\n"
        ),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "remote", "get-url", "gitea"],
        ProcessAnswer(stdout="https://old.example.com/testorg/testrepo.git\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
            "remote",
            "set-url",
            "gitea",
            "https://git.example.com/testorg/testrepo.git",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(clone_dir),
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
            str(clone_dir),
            "config",
            "--add",
            "credential.https://git.example.com.helper",
            "!devops repos gitea credential",
        ],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "checkout.defaultRemote", "origin"],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "config", "remote.gitea.tagOpt", "--no-tags"],
        ProcessAnswer(),
    )
    git_fake.answer(
        ["git", "-C", str(clone_dir), "push", "gitea", "refs/remotes/origin/main:refs/heads/main"],
        ProcessAnswer(),
    )

    result = cli("repos", "remotes", "--base-dir", str(tmp_path / "repos"))
    assert result.exit_code == 0
    assert any("set-url" in call.argv for call in git_fake.calls)


def test_remotes_helper_functions(tmp_path: Path, git_fake: GitFake) -> None:
    """Test resolution helpers and edge cases."""
    from devops_cli.gitea.remotes import (
        extract_branch_name_from_porcelain,
        read_default_branch,
        resolve_repo_owner_name,
    )

    # resolve_repo_owner_name with no slash origin
    standalone = tmp_path / "simple-repo"
    standalone.mkdir()
    git_fake.answer(
        ["git", "-C", str(standalone), "remote", "get-url", "origin"],
        ProcessAnswer(stdout="simple-repo.git\n"),
    )
    owner, name = resolve_repo_owner_name(standalone, tmp_path / "other")
    assert (owner, name) == ("unknown", "simple-repo")

    # read_default_branch fallback
    git_fake.answer(
        ["git", "-C", str(standalone), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ProcessAnswer(returncode=1, stdout=""),
    )
    assert read_default_branch(standalone) == "main"

    # extract_branch_name_from_porcelain with spaces and fallback
    b1 = extract_branch_name_from_porcelain("* refs/heads/feature:refs/heads/feature", ["main"])
    assert b1 == "feature"
    b2 = extract_branch_name_from_porcelain("malformed-line", ["fallback-branch"])
    assert b2 == "fallback-branch"
