"""Tests for the Gitea API client (#1090)."""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.gitea.client import GiteaClient
from devops_cli.gitea.exceptions import GiteaAccessBlocked, GiteaError
from devops_cli.gitea.models import (
    GiteaVersion,
)


def test_version_request() -> None:
    """version() calls /api/v1/version and returns GiteaVersion."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://git.example.com/api/v1/version"
        assert request.headers["Authorization"] == "token secret-token"
        return httpx2.Response(200, json={"version": "1.27.3"})

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token", client=client)
    res = gitea.version()
    assert res == GiteaVersion(version="1.27.3")


def test_current_user_request() -> None:
    """current_user() calls /api/v1/user with Authorization header."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://git.example.com/api/v1/user"
        assert request.headers["Authorization"] == "token secret-token"
        return httpx2.Response(200, json={"id": 42, "login": "testuser", "username": "testuser"})

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token", client=client)
    user = gitea.current_user()
    assert (user.id, user.login) == (42, "testuser")


def test_path_escaping() -> None:
    """Path segments are escaped and not malformed."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://git.example.com/api/v1/repos/special%2Fowner/my-repo"
        return httpx2.Response(
            200, json={"id": 1, "name": "my-repo", "private": True, "default_branch": "main"}
        )

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token", client=client)
    repo = gitea.repo("special/owner", "my-repo")
    assert repo is not None
    assert repo.name == "my-repo"


def test_org_get_and_create() -> None:
    """org() returns None on 404, GiteaOrg on 200; create_org() sends 201."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            if "absent" in str(request.url):
                return httpx2.Response(404, json={"message": "Not found"})
            return httpx2.Response(
                200, json={"id": 10, "name": "existing-org", "username": "existing-org"}
            )
        if request.method == "POST":
            assert str(request.url) == "https://git.example.com/api/v1/orgs"
            data = request.read().decode("utf-8")
            assert "private" in data
            return httpx2.Response(
                201,
                json={"id": 11, "name": "new-org", "username": "new-org", "visibility": "private"},
            )
        return httpx2.Response(400)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token", client=client)
    assert gitea.org("absent") is None

    existing = gitea.org("existing-org")
    assert existing is not None
    assert existing.name == "existing-org"

    created = gitea.create_org("new-org")
    assert created.name == "new-org"


def test_create_repo_user_namespace_and_org() -> None:
    """create_repo creates under /user/repos when owner is current user, else /orgs/{org}/repos."""
    requests_made: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests_made.append(request)
        if "/api/v1/user" in str(request.url) and request.method == "GET":
            return httpx2.Response(200, json={"id": 1, "login": "alice", "username": "alice"})
        if "/api/v1/user/repos" in str(request.url):
            return httpx2.Response(
                201,
                json={"id": 101, "name": "user-repo", "private": True, "default_branch": "main"},
            )
        if "/api/v1/orgs/my-org/repos" in str(request.url):
            return httpx2.Response(
                201,
                json={"id": 102, "name": "org-repo", "private": True, "default_branch": "master"},
            )
        return httpx2.Response(400)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token", client=client)

    # Repository for current user's login
    repo1 = gitea.create_repo("alice", "user-repo")
    assert (repo1.name, repo1.private) == ("user-repo", True)
    assert any("/api/v1/user/repos" in str(r.url) for r in requests_made)

    # Repository for organisation
    repo2 = gitea.create_repo("my-org", "org-repo", default_branch="master")
    assert (repo2.name, repo2.default_branch) == ("org-repo", "master")
    assert any("/api/v1/orgs/my-org/repos" in str(r.url) for r in requests_made)


def test_branch_protections_get_and_create() -> None:
    """branch_protections() and create_branch_protection()."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            return httpx2.Response(
                200,
                json=[
                    {
                        "rule_name": "main",
                        "enable_push": True,
                        "enable_force_push": False,
                        "priority": 0,
                    }
                ],
            )
        if request.method == "POST":
            return httpx2.Response(
                201,
                json={
                    "rule_name": "release/*",
                    "enable_push": True,
                    "enable_force_push": False,
                    "priority": 1,
                },
            )
        return httpx2.Response(400)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token", client=client)
    rules = gitea.branch_protections("org", "repo")
    assert len(rules) == 1
    assert rules[0].rule_name == "main"

    created = gitea.create_branch_protection(
        "org", "repo", rule_name="release/*", enable_push=True, enable_force_push=False, priority=1
    )
    assert (created.rule_name, created.priority) == ("release/*", 1)


def test_cloudflare_access_redirect_raises_blocked() -> None:
    """A redirect to another host raises GiteaAccessBlocked without leaking the token."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            302, headers={"Location": "https://access.cloudflareaccess.com/login"}
        )

    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=False)
    gitea = GiteaClient("https://git.example.com", "secret-token-xyz", client=client)

    with pytest.raises(GiteaAccessBlocked) as exc:
        gitea.version()
    assert "bypass" in str(exc.value).lower()
    assert "secret-token-xyz" not in str(exc.value)


def test_cloudflare_challenge_raises_blocked() -> None:
    """A 403 with cf-mitigated: challenge raises GiteaAccessBlocked without leaking the token."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            403, headers={"cf-mitigated": "challenge"}, text="Cloudflare challenge"
        )

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token-xyz", client=client)

    with pytest.raises(GiteaAccessBlocked) as exc:
        gitea.version()
    assert "challenge" in str(exc.value).lower() or "bypass" in str(exc.value).lower()
    assert "secret-token-xyz" not in str(exc.value)


def test_gitea_error_masks_token() -> None:
    """GiteaError masks secrets from the error message."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        if "/api/v1/user" in str(request.url) and request.method == "GET":
            return httpx2.Response(200, json={"id": 1, "login": "testuser", "username": "testuser"})
        return httpx2.Response(
            500, json={"message": "Internal error with token secret-token-xyz for repo"}
        )

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "secret-token-xyz", client=client)

    with pytest.raises(GiteaError) as exc:
        gitea.create_repo("org", "my-repo")
    assert "secret-token-xyz" not in str(exc.value)
    assert "create_repo" in str(exc.value)


def test_gitea_client_check_error_non_json_body() -> None:
    """_check_error handles plain-text (non-JSON) error bodies."""

    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(502, text="Bad Gateway html page")

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    gitea = GiteaClient("https://git.example.com", "token-123", client=client)
    with pytest.raises(GiteaError) as exc:
        gitea.version()
    assert "Bad Gateway html page" in str(exc.value)
    gitea.close()


def test_gitea_access_blocked_masks_token_in_reason() -> None:
    """GiteaAccessBlocked masks token if present in reason."""
    exc = GiteaAccessBlocked("Custom reason with secret-tok", token="secret-tok")
    assert "secret-tok" not in str(exc)
    assert "[REDACTED]" in str(exc)


def test_gitea_models_username_and_login_fallbacks() -> None:
    """Gitea models validate login/username and name/username bidirectional fallbacks."""
    from devops_cli.gitea.models import GiteaOrg, GiteaUser

    u1 = GiteaUser.model_validate({"id": 1, "username": "bob"})
    assert u1.login == "bob"
    u2 = GiteaUser.model_validate({"id": 2, "login": "carol"})
    assert u2.username == "carol"

    o1 = GiteaOrg.model_validate({"username": "devops-org"})
    assert o1.name == "devops-org"
    o2 = GiteaOrg.model_validate({"name": "sales-org"})
    assert o2.username == "sales-org"
