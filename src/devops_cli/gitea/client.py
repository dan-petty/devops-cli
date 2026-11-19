"""Gitea API client (#1090)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx2

from devops_cli.gitea.exceptions import GiteaAccessBlocked, GiteaError
from devops_cli.gitea.models import (
    GiteaBranchProtection,
    GiteaOrg,
    GiteaRepo,
    GiteaUser,
    GiteaVersion,
)
from devops_cli.http.egress import configured_level
from devops_cli.http.entry import http_client

if TYPE_CHECKING:
    from types import TracebackType

    from devops_cli.http.egress import EgressLevel


class GiteaClient:
    """Synchronous Gitea REST API client wrapping httpx2."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        client: httpx2.Client | None = None,
        egress_level: EgressLevel | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v1"
        self.token = token
        self._cached_user: GiteaUser | None = None
        self._owned_client = client is None

        if client is not None:
            self._client = client
        else:
            level = egress_level or configured_level()
            self._client = http_client(
                level,
                base_url=self.api_url,
                headers={"Authorization": f"token {token}"},
                follow_redirects=False,
                verify=True,
            )

    def close(self) -> None:
        """Close the underlying client if owned."""
        if self._owned_client:
            self._client.close()

    def __enter__(self) -> GiteaClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: Any = None,
        params: dict[str, Any] | None = None,
    ) -> httpx2.Response:
        url = f"{self.api_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"token {self.token}"}
        response = self._client.request(
            method,
            url,
            headers=headers,
            json=json_data,
            params=params,
        )

        if response.is_redirect:
            loc = response.headers.get("Location", "another host")
            raise GiteaAccessBlocked(f"redirected to {loc}", token=self.token)

        if response.status_code == 403 and response.headers.get("cf-mitigated") == "challenge":
            raise GiteaAccessBlocked("Cloudflare challenge", token=self.token)

        return response

    def _check_error(
        self,
        response: httpx2.Response,
        call_name: str,
        repo: str | None = None,
    ) -> None:
        if response.is_error:
            try:
                body = response.json()
                msg = body.get("message") if isinstance(body, dict) else str(body)
            except ValueError, KeyError:
                msg = response.text or f"HTTP {response.status_code}"
            target = f" for {repo}" if repo else ""
            raise GiteaError(f"{call_name}{target}: {msg}", token=self.token)

    def version(self) -> GiteaVersion:
        """GET /api/v1/version."""
        resp = self._request("GET", "version")
        self._check_error(resp, "version")
        return GiteaVersion.model_validate(resp.json())

    def current_user(self) -> GiteaUser:
        """GET /api/v1/user."""
        resp = self._request("GET", "user")
        self._check_error(resp, "current_user")
        user = GiteaUser.model_validate(resp.json())
        self._cached_user = user
        return user

    def org(self, name: str) -> GiteaOrg | None:
        """GET /api/v1/orgs/{org}."""
        escaped = quote(name, safe="")
        resp = self._request("GET", f"orgs/{escaped}")
        if resp.status_code == 404:
            return None
        self._check_error(resp, "org")
        return GiteaOrg.model_validate(resp.json())

    def create_org(self, name: str, *, visibility: str = "private") -> GiteaOrg:
        """POST /api/v1/orgs."""
        payload = {"username": name, "visibility": visibility}
        resp = self._request("POST", "orgs", json_data=payload)
        self._check_error(resp, "create_org")
        return GiteaOrg.model_validate(resp.json())

    def repo(self, owner: str, name: str) -> GiteaRepo | None:
        """GET /api/v1/repos/{owner}/{name}."""
        escaped_owner = quote(owner, safe="")
        escaped_name = quote(name, safe="")
        resp = self._request("GET", f"repos/{escaped_owner}/{escaped_name}")
        if resp.status_code == 404:
            return None
        self._check_error(resp, "repo", repo=f"{owner}/{name}")
        return GiteaRepo.model_validate(resp.json())

    def create_repo(
        self,
        owner: str,
        name: str,
        *,
        private: bool = True,
        auto_init: bool = False,
        default_branch: str | None = None,
    ) -> GiteaRepo:
        """POST /api/v1/user/repos or /api/v1/orgs/{owner}/repos."""
        if self._cached_user is None:
            self._cached_user = self.current_user()

        is_user = owner == self._cached_user.login
        payload: dict[str, Any] = {
            "name": name,
            "private": private,
            "auto_init": auto_init,
        }
        if default_branch:
            payload["default_branch"] = default_branch

        if is_user:
            path = "user/repos"
        else:
            escaped_owner = quote(owner, safe="")
            path = f"orgs/{escaped_owner}/repos"

        resp = self._request("POST", path, json_data=payload)
        self._check_error(resp, "create_repo", repo=f"{owner}/{name}")
        return GiteaRepo.model_validate(resp.json())

    def branch_protections(self, owner: str, repo: str) -> list[GiteaBranchProtection]:
        """GET /api/v1/repos/{owner}/{repo}/branch_protections."""
        escaped_owner = quote(owner, safe="")
        escaped_repo = quote(repo, safe="")
        resp = self._request("GET", f"repos/{escaped_owner}/{escaped_repo}/branch_protections")
        self._check_error(resp, "branch_protections", repo=f"{owner}/{repo}")
        raw = resp.json()
        if not isinstance(raw, list):
            return []
        return [GiteaBranchProtection.model_validate(item) for item in raw]

    def create_branch_protection(
        self,
        owner: str,
        repo: str,
        *,
        rule_name: str,
        enable_push: bool = True,
        enable_force_push: bool = False,
        priority: int = 0,
    ) -> GiteaBranchProtection:
        """POST /api/v1/repos/{owner}/{repo}/branch_protections."""
        escaped_owner = quote(owner, safe="")
        escaped_repo = quote(repo, safe="")
        payload = {
            "rule_name": rule_name,
            "enable_push": enable_push,
            "enable_force_push": enable_force_push,
            "priority": priority,
        }
        resp = self._request(
            "POST",
            f"repos/{escaped_owner}/{escaped_repo}/branch_protections",
            json_data=payload,
        )
        self._check_error(resp, "create_branch_protection", repo=f"{owner}/{repo}")
        return GiteaBranchProtection.model_validate(resp.json())

    def branch(self, owner: str, repo: str, branch: str) -> dict[str, Any] | None:
        """GET /api/v1/repos/{owner}/{repo}/branches/{branch}."""
        escaped_owner = quote(owner, safe="")
        escaped_repo = quote(repo, safe="")
        escaped_branch = quote(branch, safe="")
        resp = self._request(
            "GET", f"repos/{escaped_owner}/{escaped_repo}/branches/{escaped_branch}"
        )
        if resp.status_code == 404:
            return None
        self._check_error(resp, "branch", repo=f"{owner}/{repo}")
        raw = resp.json()
        return raw if isinstance(raw, dict) else None

    def contents(self, owner: str, repo: str, path: str, *, ref: str | None = None) -> Any | None:
        """GET /api/v1/repos/{owner}/{repo}/contents/{path}."""
        escaped_owner = quote(owner, safe="")
        escaped_repo = quote(repo, safe="")
        escaped_path = quote(path.lstrip("/"), safe="/")
        params = {"ref": ref} if ref else None
        resp = self._request(
            "GET",
            f"repos/{escaped_owner}/{escaped_repo}/contents/{escaped_path}",
            params=params,
        )
        if resp.status_code == 404:
            return None
        self._check_error(resp, "contents", repo=f"{owner}/{repo}")
        return resp.json()
