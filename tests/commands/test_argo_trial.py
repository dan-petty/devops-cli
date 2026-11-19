"""Tests for devops argo cd trial commands (#1082)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest
import typer
from typer.testing import CliRunner

import devops_cli.argo.trial as argo_trial
import devops_cli.gitea.client as gitea_client
from devops_cli.argo.trial import (
    DEFAULT_TRIAL_REPO,
    TRIAL_PROJECT,
    branch_to_dns_label,
    build_trial_application_manifest,
    build_trial_namespace_manifest,
    normalize_trial_name,
)
from devops_cli.exceptions.argo import ArgoResourceNotFoundError
from devops_cli.main import app as main_app

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner()


def test_branch_to_dns_label() -> None:
    """branch_to_dns_label converts branches with slashes, capitals, and special chars."""
    assert branch_to_dns_label("try/smoke") == "try-smoke"
    assert branch_to_dns_label("feat/My_Super_Feature") == "feat-my-super-feature"
    assert branch_to_dns_label("---test---") == "test"
    assert branch_to_dns_label("") == "trial"


def test_normalize_trial_name() -> None:
    """normalize_trial_name ensures the 'trial-' prefix and valid RFC 1123 name."""
    assert normalize_trial_name("smoke") == "trial-smoke"
    assert normalize_trial_name("trial-smoke") == "trial-smoke"
    with pytest.raises(typer.Exit) as raised:
        normalize_trial_name("Invalid Name!")
    assert raised.value.exit_code == 1


def test_rendered_manifest_structures() -> None:
    """Verify structural tuples for rendered Namespace and Application manifests."""
    ns = build_trial_namespace_manifest("feature-x")
    ns_tuple = (
        ns["metadata"]["name"],
        ns["metadata"]["labels"]["app.kubernetes.io/managed-by"],
        ns["metadata"]["labels"]["pod-security.kubernetes.io/enforce"],
        ns["metadata"]["labels"]["pod-security.kubernetes.io/warn"],
        ns["metadata"]["labels"]["pod-security.kubernetes.io/audit"],
    )
    assert ns_tuple == (
        "trial-feature-x",
        "devops-cli",
        "restricted",
        "restricted",
        "restricted",
    )

    app = build_trial_application_manifest(
        "feature-x",
        branch="feat/feature-x",
        path="k8s/apps/demo",
        repo="dan-petty/devops-cli",
    )
    sync_policy = app["spec"]["syncPolicy"]
    app_tuple = (
        app["metadata"]["name"],
        app["metadata"]["namespace"],
        tuple(app["metadata"]["finalizers"]),
        app["spec"]["project"],
        app["spec"]["source"]["repoURL"],
        app["spec"]["source"]["targetRevision"],
        app["spec"]["source"]["path"],
        app["spec"]["destination"]["server"],
        app["spec"]["destination"]["namespace"],
        sync_policy["automated"]["prune"],
        sync_policy["automated"]["selfHeal"],
        "CreateNamespace" in str(sync_policy),
    )
    assert app_tuple == (
        "trial-feature-x",
        "argocd",
        ("resources-finalizer.argocd.argoproj.io",),
        TRIAL_PROJECT,
        f"http://gitea-http.gitea.svc.cluster.local:3000/{DEFAULT_TRIAL_REPO}.git",
        "feat/feature-x",
        "k8s/apps/demo",
        "https://kubernetes.default.svc",
        "trial-feature-x",
        True,
        True,
        False,  # No CreateNamespace
    )


class RecordingCRDService:
    """Stub ArgoCRDService recording applications and resources."""

    def __init__(self) -> None:
        self.applied: list[dict[str, Any]] = []
        self.deleted: list[tuple[str, str]] = []
        self.resources: dict[str, dict[str, Any]] = {}

    def apply_application(self, manifest: dict[str, Any], namespace: str = "argocd") -> Any:
        self.applied.append(manifest)
        name = manifest["metadata"]["name"]
        self.resources[name] = manifest
        stub = MagicMock()
        stub.name = name
        return stub

    def delete_application(self, name: str, namespace: str = "argocd") -> dict[str, Any]:
        self.deleted.append((name, namespace))
        self.resources.pop(name, None)
        return {"status": "Success"}

    def get_resource(self, plural: str, name: str, namespace: str = "argocd") -> dict[str, Any]:
        if name in self.resources:
            return self.resources[name]
        raise ArgoResourceNotFoundError(
            f"Application {name} not found", resource=name, namespace=namespace
        )

    def list_resources(self, plural: str, namespace: str = "argocd") -> list[dict[str, Any]]:
        return list(self.resources.values())


@pytest.fixture
def recording_crd(monkeypatch: pytest.MonkeyPatch) -> RecordingCRDService:
    stub = RecordingCRDService()
    monkeypatch.setattr(argo_trial, "get_argo_crd_service", lambda context=None: stub)
    return stub


def _fake_gitea_transport(
    *,
    branch_exists: bool = True,
    path_exists: bool = True,
    blocked: bool = False,
) -> httpx2.MockTransport:
    def handler(request: httpx2.Request) -> httpx2.Response:
        url = str(request.url)
        if blocked:
            return httpx2.Response(302, headers={"Location": "https://external.example.com"})
        if "/branches/" in url:
            if branch_exists:
                return httpx2.Response(200, json={"name": "my-branch", "commit": {"id": "1234"}})
            return httpx2.Response(404, json={"message": "Branch not found"})
        if "/contents/" in url:
            if path_exists:
                return httpx2.Response(200, json=[{"name": "file.yaml", "type": "file"}])
            return httpx2.Response(404, json={"message": "Path not found"})
        return httpx2.Response(200, json={})

    return httpx2.MockTransport(handler)


def test_trial_start_success(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial start verifies Gitea branch and path, applies Namespace and Application."""
    transport = _fake_gitea_transport(branch_exists=True, path_exists=True)
    client = httpx2.Client(transport=transport)
    monkeypatch.setattr(gitea_client, "http_client", lambda *a, **kw: client)
    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url="http://git.local", token="secret-token"),
            gitea_token="secret-token",
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: "secret-token")
    applied_namespaces: list[str] = []
    monkeypatch.setattr(
        argo_trial,
        "apply_trial_namespace",
        lambda name, context=None: applied_namespaces.append(name),
    )

    res = runner.invoke(
        main_app,
        [
            "argo",
            "cd",
            "trial",
            "start",
            "--branch",
            "try/smoke",
            "--path",
            "k8s/trial-smoke",
        ],
    )
    assert res.exit_code == 0
    assert "Trial Application 'trial-try-smoke' created in project 'trial'" in res.output
    assert applied_namespaces == ["try-smoke"]
    assert len(recording_crd.applied) == 1
    assert recording_crd.applied[0]["metadata"]["name"] == "trial-try-smoke"


def test_trial_start_refusal_when_branch_missing(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial start fails and applies nothing when branch is missing on Gitea."""
    transport = _fake_gitea_transport(branch_exists=False)
    client = httpx2.Client(transport=transport)
    monkeypatch.setattr(gitea_client, "http_client", lambda *a, **kw: client)
    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url="http://git.local", token="secret-token"),
            gitea_token="secret-token",
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: "secret-token")
    applied_namespaces: list[str] = []
    monkeypatch.setattr(
        argo_trial,
        "apply_trial_namespace",
        lambda name, context=None: applied_namespaces.append(name),
    )

    res = runner.invoke(
        main_app,
        [
            "argo",
            "cd",
            "trial",
            "start",
            "--branch",
            "missing-branch",
            "--path",
            "k8s/app",
        ],
    )
    assert res.exit_code == 1
    assert "does not exist on Gitea repository" in res.output
    assert applied_namespaces == []
    assert recording_crd.applied == []


def test_trial_start_refusal_when_path_missing(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial start fails and applies nothing when path is missing on Gitea."""
    transport = _fake_gitea_transport(branch_exists=True, path_exists=False)
    client = httpx2.Client(transport=transport)
    monkeypatch.setattr(gitea_client, "http_client", lambda *a, **kw: client)
    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url="http://git.local", token="secret-token"),
            gitea_token="secret-token",
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: "secret-token")
    applied_namespaces: list[str] = []
    monkeypatch.setattr(
        argo_trial,
        "apply_trial_namespace",
        lambda name, context=None: applied_namespaces.append(name),
    )

    res = runner.invoke(
        main_app,
        [
            "argo",
            "cd",
            "trial",
            "start",
            "--branch",
            "my-branch",
            "--path",
            "k8s/missing",
        ],
    )
    assert res.exit_code == 1
    assert "does not exist on branch" in res.output
    assert applied_namespaces == []
    assert recording_crd.applied == []


def test_trial_start_gitea_access_blocked(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial start exits 1 with message when GiteaAccessBlocked is raised."""
    transport = _fake_gitea_transport(blocked=True)
    client = httpx2.Client(transport=transport)
    monkeypatch.setattr(gitea_client, "http_client", lambda *a, **kw: client)
    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url="http://git.local", token="secret-token"),
            gitea_token="secret-token",
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: "secret-token")

    res = runner.invoke(
        main_app,
        ["argo", "cd", "trial", "start", "--branch", "my-branch", "--path", "k8s/app"],
    )
    assert res.exit_code == 1
    assert "blocked" in res.output.lower() or "redirected" in res.output.lower()
    assert recording_crd.applied == []


def test_trial_start_unconfigured_gitea_names_1081(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Gitea is not configured (e.g. minikube), start fails naming #1081."""
    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url=None, token=None),
            gitea_token=None,
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: None)

    res = runner.invoke(
        main_app,
        ["argo", "cd", "trial", "start", "--branch", "my-branch", "--path", "k8s/app"],
    )
    assert res.exit_code == 1
    assert "#1081" in res.output
    assert recording_crd.applied == []


def test_trial_start_dry_run_applies_nothing(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial start with --dry-run prints Application YAML and applies nothing."""
    transport = _fake_gitea_transport(branch_exists=True, path_exists=True)
    client = httpx2.Client(transport=transport)
    monkeypatch.setattr(gitea_client, "http_client", lambda *a, **kw: client)
    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url="http://git.local", token="secret-token"),
            gitea_token="secret-token",
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: "secret-token")
    applied_namespaces: list[str] = []
    monkeypatch.setattr(
        argo_trial,
        "apply_trial_namespace",
        lambda name, context=None: applied_namespaces.append(name),
    )

    res = runner.invoke(
        main_app,
        [
            "argo",
            "cd",
            "trial",
            "start",
            "--branch",
            "try/smoke",
            "--path",
            "k8s/trial-smoke",
            "--dry-run",
        ],
    )
    assert res.exit_code == 0
    assert "kind: Application" in res.output
    assert "project: trial" in res.output
    assert applied_namespaces == []
    assert recording_crd.applied == []


def test_trial_end_success(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial end deletes Application, waits for it, and deletes Namespace."""
    # Seed Application
    recording_crd.resources["trial-smoke"] = {"metadata": {"name": "trial-smoke"}}
    deleted_namespaces: list[str] = []
    monkeypatch.setattr(
        argo_trial,
        "delete_trial_namespace",
        lambda name, context=None: deleted_namespaces.append(name),
    )

    res = runner.invoke(
        main_app,
        ["argo", "cd", "trial", "end", "smoke"],
    )
    assert res.exit_code == 0
    assert "Trial 'trial-smoke' ended and Namespace 'trial-smoke' deleted." in res.output
    assert recording_crd.deleted == [("trial-smoke", "argocd")]
    assert deleted_namespaces == ["trial-smoke"]


def test_trial_end_invalid_name_refused(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial end refuses invalid RFC 1123 names."""
    res = runner.invoke(
        main_app,
        ["argo", "cd", "trial", "end", "Invalid_Name!"],
    )
    assert res.exit_code != 0
    assert recording_crd.deleted == []


def test_trial_end_dry_run_deletes_nothing(
    recording_crd: RecordingCRDService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trial end with --dry-run prints plan and deletes nothing."""
    recording_crd.resources["trial-smoke"] = {"metadata": {"name": "trial-smoke"}}
    deleted_namespaces: list[str] = []
    monkeypatch.setattr(
        argo_trial,
        "delete_trial_namespace",
        lambda name, context=None: deleted_namespaces.append(name),
    )

    res = runner.invoke(
        main_app,
        ["argo", "cd", "trial", "end", "smoke", "--dry-run"],
    )
    assert res.exit_code == 0
    assert "Would delete Application 'trial-smoke'" in res.output
    assert recording_crd.deleted == []
    assert deleted_namespaces == []


def test_trial_list(
    recording_crd: RecordingCRDService,
) -> None:
    """Trial list filters applications to project 'trial' and renders table."""
    recording_crd.resources["trial-1"] = {
        "metadata": {"name": "trial-1", "creationTimestamp": "2026-10-01T12:00:00Z"},
        "spec": {
            "project": "trial",
            "source": {"targetRevision": "feat/1", "path": "k8s/app1"},
        },
        "status": {
            "sync": {"status": "Synced"},
            "health": {"status": "Healthy"},
        },
    }
    # Non-trial application should be excluded
    recording_crd.resources["homelab-root"] = {
        "metadata": {"name": "homelab-root"},
        "spec": {"project": "default"},
    }

    res = runner.invoke(
        main_app,
        ["argo", "cd", "trial", "list"],
    )
    assert res.exit_code == 0
    assert "trial-1" in res.output
    assert "feat/1" in res.output
    assert "k8s/app1" in res.output
    assert "homelab-root" not in res.output


def test_trial_list_dry_run() -> None:
    """Trial list with --dry-run prints request plan."""
    res = runner.invoke(
        main_app,
        ["argo", "cd", "trial", "list", "--dry-run"],
    )
    assert res.exit_code == 0
    assert "Plan for listing Argo CD trial applications" in res.output
    assert "CustomObjectsApi.list_namespaced_custom_object" in res.output


def test_apply_trial_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """apply_trial_namespace runs kubectl and handles errors."""
    from devops_cli.argo.trial import apply_trial_namespace
    from devops_cli.exceptions.argo import ArgoError

    monkeypatch.setattr(
        argo_trial,
        "run_subprocess",
        lambda cmd, input=None, quiet=True, timeout=30.0: MagicMock(returncode=0),
    )
    apply_trial_namespace("trial-test")

    monkeypatch.setattr(
        argo_trial,
        "run_subprocess",
        lambda cmd, input=None, quiet=True, timeout=30.0: MagicMock(
            returncode=1, stderr="permission denied"
        ),
    )
    with pytest.raises(
        ArgoError, match="Failed to apply Namespace 'trial-test': permission denied"
    ):
        apply_trial_namespace("trial-test")


def test_delete_trial_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """delete_trial_namespace runs kubectl delete and handles errors."""
    from devops_cli.argo.trial import delete_trial_namespace
    from devops_cli.exceptions.argo import ArgoError

    monkeypatch.setattr(
        argo_trial,
        "run_subprocess",
        lambda cmd, quiet=True, timeout=60.0: MagicMock(returncode=0),
    )
    delete_trial_namespace("trial-test")

    monkeypatch.setattr(
        argo_trial,
        "run_subprocess",
        lambda cmd, quiet=True, timeout=60.0: MagicMock(returncode=1, stderr="deletion failed"),
    )
    with pytest.raises(ArgoError, match="Failed to delete Namespace 'trial-test': deletion failed"):
        delete_trial_namespace("trial-test")


def test_check_gitea_branch_and_path_invalid_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_gitea_branch_and_path refuses invalid repo format."""
    from devops_cli.argo.trial import check_gitea_branch_and_path
    from devops_cli.exceptions.argo import ArgoError

    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url="http://git.local", token="token"),
            gitea_token="token",
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: "token")

    with pytest.raises(ArgoError, match="Invalid repository 'invalidrepo'"):
        check_gitea_branch_and_path(
            "main",
            "k8s",
            repo="invalidrepo",
        )


def test_check_gitea_branch_and_path_gitea_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_gitea_branch_and_path handles GiteaError."""
    from devops_cli.argo.trial import check_gitea_branch_and_path
    from devops_cli.exceptions.argo import ArgoError
    from devops_cli.exceptions.gitea import GiteaError

    class FailingClient:
        def __enter__(self) -> FailingClient:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def branch(self, *args: Any, **kwargs: Any) -> Any:
            raise GiteaError("API down")

    monkeypatch.setattr(
        argo_trial,
        "load_settings",
        lambda: MagicMock(
            gitea=MagicMock(url="http://git.local", token="token"),
            gitea_token="token",
        ),
    )
    monkeypatch.setattr(argo_trial, "get_gitea_token", lambda s: "token")
    monkeypatch.setattr(argo_trial, "GiteaClient", lambda url, token: FailingClient())
    with pytest.raises(ArgoError, match="Gitea error while inspecting"):
        check_gitea_branch_and_path(
            "main",
            "k8s",
            repo="owner/repo",
        )


def test_end_trial_crd_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """end_trial handles missing application gracefully."""
    from devops_cli.argo.trial import end_trial

    class MissingCRDService:
        def delete_application(self, name: str, namespace: str = "argocd") -> dict[str, Any]:
            raise ArgoResourceNotFoundError("app not found")

        def get_resource(self, plural: str, name: str, namespace: str = "argocd") -> dict[str, Any]:
            raise ArgoResourceNotFoundError("app not found")

    monkeypatch.setattr(
        argo_trial, "get_argo_crd_service", lambda context=None: MissingCRDService()
    )
    deleted_ns: list[str] = []
    monkeypatch.setattr(
        argo_trial,
        "delete_trial_namespace",
        lambda name, context=None: deleted_ns.append(name),
    )
    assert end_trial("smoke") == "trial-smoke"
    assert deleted_ns == ["trial-smoke"]


def test_end_trial_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """end_trial raises ArgoError when application deletion times out."""
    from devops_cli.argo.trial import end_trial
    from devops_cli.exceptions.argo import ArgoError

    class ExistingCRDService:
        def delete_application(self, name: str, namespace: str = "argocd") -> dict[str, Any]:
            return {}

        def get_resource(self, plural: str, name: str, namespace: str = "argocd") -> dict[str, Any]:
            return {"metadata": {"name": name}}

    monkeypatch.setattr(
        argo_trial, "get_argo_crd_service", lambda context=None: ExistingCRDService()
    )
    with pytest.raises(ArgoError, match="Timed out waiting for Application"):
        end_trial("smoke", timeout_seconds=-1)


def test_trial_end_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """cd_trial_end handles ArgoError gracefully."""
    from devops_cli.exceptions.argo import ArgoError

    monkeypatch.setattr(
        argo_trial,
        "end_trial",
        lambda name, context=None, dry_run=False: (_ for _ in ()).throw(ArgoError("end failed")),
    )
    res = runner.invoke(main_app, ["argo", "cd", "trial", "end", "smoke"])
    assert res.exit_code == 1
    assert "end failed" in res.output


def test_trial_list_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """cd_trial_list handles ArgoError gracefully."""
    from devops_cli.exceptions.argo import ArgoError

    monkeypatch.setattr(
        argo_trial,
        "list_trials",
        lambda context=None: (_ for _ in ()).throw(ArgoError("list failed")),
    )
    res = runner.invoke(main_app, ["argo", "cd", "trial", "list"])
    assert res.exit_code == 1
    assert "list failed" in res.output
