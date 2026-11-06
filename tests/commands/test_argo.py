"""Tests for argo command input validation and CLI execution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.argo import _validate_k8s_name
from devops_cli.commands.argo import app as argo_app
from devops_cli.k8s.service import KubernetesService
from devops_cli.main import app as main_app
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.kubernetes import FakeCluster

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner()


@pytest.fixture
def local_argocd(config: Callable[..., Path]) -> str:
    """Point devops-cli at a fake Argo CD on the loopback host; return its URL."""
    url = "http://localhost:8080"
    config(argocd={"url": url})
    return url


def _serve_argocd(web: WebFake, applications: dict[str, Any], application: dict[str, Any]) -> None:
    """Serve Argo CD at `local_argocd`: the application list, one application, and the sync."""

    def server(request: httpx2.Request) -> httpx2.Response | None:
        if request.method == "POST":
            return httpx2.Response(200, json={"status": "Synced"})
        if request.url.path.endswith("/applications"):
            return httpx2.Response(200, json=applications)
        return httpx2.Response(200, json=application)

    web.serve(server)


@pytest.mark.parametrize(
    "value",
    [
        "my-namespace",
        "namespace1",
        "a",
        "ab",
        "x" * 63,
    ],
)
def test_valid_k8s_label_names(value: str) -> None:
    assert _validate_k8s_name(value, "namespace", namespace=True) is None


@pytest.mark.parametrize(
    "value",
    [
        "; rm -rf /",
        "",
        "UPPERCASE",
        "-leading-dash",
        "trailing-dash-",
        "has.dot",  # dots not allowed in namespace (RFC 1123 label)
        "x" * 64,  # exceeds 63-char label limit
        "../etc/passwd",
        "a b",
    ],
)
def test_invalid_k8s_label_names_rejected(value: str) -> None:
    with pytest.raises(typer.Exit) as raised:
        _validate_k8s_name(value, "namespace", namespace=True)
    assert raised.value.exit_code == 1


@pytest.mark.parametrize(
    "value",
    [
        "my-workflow",
        "workflow.v2",  # dots allowed in resource names (RFC 1123 subdomain)
        "a",
        "x" * 253,
    ],
)
def test_valid_k8s_resource_names(value: str) -> None:
    assert _validate_k8s_name(value, "workflow name") is None


@pytest.mark.parametrize(
    "value",
    [
        "; rm -rf /",
        "",
        "UPPERCASE",
        "-leading",
        "trailing-",
        "x" * 254,  # exceeds 253-char subdomain limit
        "has space",
    ],
)
def test_invalid_k8s_resource_names_rejected(value: str) -> None:
    with pytest.raises(typer.Exit) as raised:
        _validate_k8s_name(value, "workflow name")
    assert raised.value.exit_code == 1


CHART_REPO = "https://charts.example.com/helm"
GIT_REPO = "https://git.example.com/org/values.git"
SINGLE_REPO = "https://git.example.com/org/single.git"


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ({"source": {"repoURL": SINGLE_REPO}}, SINGLE_REPO),
        (
            {"sources": [{"repoURL": CHART_REPO}, {"repoURL": GIT_REPO, "ref": "values"}]},
            CHART_REPO,
        ),
        (
            {"source": {"repoURL": SINGLE_REPO}, "sources": [{"repoURL": CHART_REPO}]},
            CHART_REPO,
        ),
        ({}, ""),
        ({"source": {"repoURL": SINGLE_REPO}, "sources": []}, SINGLE_REPO),
        ({"sources": "x"}, ""),
        ({"sources": [None]}, ""),
    ],
    ids=["source", "sources", "both", "neither", "empty-sources", "str-sources", "none-entry"],
)
def test_argocd_app_repo_url_follows_argo_source_order(spec: dict[str, Any], expected: str) -> None:
    """The repo is the first of `spec.sources`, else `spec.source`, as Argo CD reads it (#2579)."""
    from devops_cli.models.argo import ArgoCDApp

    assert ArgoCDApp.from_api_item({"spec": spec}).repo_url == expected


def test_argocd_app_from_api_item() -> None:
    """Verify ArgoCDApp parses full and partial API responses."""
    from devops_cli.models.argo import ArgoCDApp

    item = {
        "metadata": {"name": "frontend-app"},
        "spec": {"project": "default", "source": {"repoURL": "https://github.com/org/repo.git"}},
        "status": {
            "sync": {"status": "Synced", "revision": "abcdef123456789"},
            "health": {"status": "Healthy"},
        },
    }
    app_obj = ArgoCDApp.from_api_item(item)
    assert app_obj.name == "frontend-app"
    assert app_obj.project == "default"
    assert app_obj.sync_status == "Synced"
    assert app_obj.health_status == "Healthy"
    assert app_obj.repo_url == "https://github.com/org/repo.git"
    assert app_obj.revision == "abcdef12"

    empty_app = ArgoCDApp.from_api_item({})
    assert empty_app.name == ""
    assert empty_app.sync_status == "Unknown"
    assert empty_app.health_status == "Unknown"

    non_dict_item = {
        "metadata": "invalid_meta",
        "spec": 123,
        "status": False,
    }
    non_dict_app = ArgoCDApp.from_api_item(non_dict_item)  # type: ignore[arg-type]
    assert non_dict_app.name == ""
    assert non_dict_app.project == ""

    nested_non_dict_item = {
        "metadata": {},
        "spec": {"source": "invalid_source"},
        "status": {"sync": "invalid_sync", "health": "invalid_health"},
    }
    nested_app = ArgoCDApp.from_api_item(nested_non_dict_item)  # type: ignore[arg-type]
    assert nested_app.repo_url == ""
    assert nested_app.sync_status == "Unknown"
    assert nested_app.health_status == "Unknown"


def test_argo_commands_execution(tmp_path: Path, web: WebFake, local_argocd: str) -> None:
    """Verify argo cd, workflows, and rollouts subcommands.

    The first command turns the global dry run on, and it stays on until the bootstrap step, so
    the `cd apps` commands send no request. Their live requests have their own tests.
    """
    sample_wf = tmp_path / "workflow.yaml"
    sample_wf.write_text(
        "apiVersion: argoproj.io/v1alpha1\nkind: Workflow\nmetadata:\n  name: my-wf\n",
        encoding="utf-8",
    )

    # Argo custom resources are read and mutated in-process via CustomObjectsApi.
    mock_crd_api = MagicMock()
    mock_crd_api.list_namespaced_custom_object.return_value = {"items": []}
    mock_crd_api.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "my-wf", "namespace": "argocd"},
        "status": {"phase": "Succeeded", "nodes": {}},
    }
    mock_crd_api.create_namespaced_custom_object.return_value = {
        "metadata": {"name": "my-wf", "namespace": "argocd"},
        "status": {"phase": "Running"},
    }

    with (
        patch("devops_cli.argo.crd.ArgoCRDService._api", return_value=mock_crd_api),
        patch("devops_cli.watchers.live_resource.LiveResourceWatcher.watch"),
    ):
        res_dry_main = runner.invoke(main_app, ["--dry-run", "argo", "cd", "apps", "list"])
        assert res_dry_main.exit_code == 0

        res_list = runner.invoke(argo_app, ["cd", "apps", "list"])
        assert res_list.exit_code == 0

        res_status = runner.invoke(argo_app, ["cd", "apps", "status", "guestbook"])
        assert res_status.exit_code == 0

        res_sync = runner.invoke(argo_app, ["cd", "apps", "sync", "guestbook"])
        assert res_sync.exit_code == 0
        assert web.recorded == []

        res_wf_list = runner.invoke(argo_app, ["workflows", "list", "--namespace", "argocd"])
        assert res_wf_list.exit_code == 0

        res_wf_submit = runner.invoke(
            argo_app, ["workflows", "submit", str(sample_wf), "--namespace", "argocd", "--wait"]
        )
        assert res_wf_submit.exit_code == 0

        res_wf_logs = runner.invoke(
            argo_app, ["workflows", "logs", "my-wf", "--namespace", "argocd", "--follow"]
        )
        assert res_wf_logs.exit_code == 0

        res_ro_list = runner.invoke(argo_app, ["rollouts", "list", "--namespace", "argocd"])
        assert res_ro_list.exit_code == 0

        res_ro_status = runner.invoke(
            argo_app, ["rollouts", "status", "my-rollout", "--namespace", "argocd", "--watch"]
        )
        assert res_ro_status.exit_code == 0

        # Test bootstrap-gitops dry-run
        res_bg_dry = runner.invoke(
            main_app,
            [
                "--dry-run",
                "argo",
                "cd",
                "apps",
                "bootstrap-gitops",
                "--root-app",
                str(sample_wf),
            ],
        )
        assert res_bg_dry.exit_code == 0
        from devops_cli.dry_run import set_dry_run

        set_dry_run(False)

        # Test bootstrap-gitops execution
        res_bg = runner.invoke(
            argo_app,
            [
                "cd",
                "apps",
                "bootstrap-gitops",
                "--root-app",
                str(sample_wf),
                "--context",
                "minikube",
            ],
        )
        assert res_bg.exit_code == 0

        # Test bootstrap-gitops missing manifest
        res_bg_missing = runner.invoke(
            argo_app,
            [
                "cd",
                "apps",
                "bootstrap-gitops",
                "--root-app",
                str(tmp_path / "nonexistent.yaml"),
            ],
        )
        assert res_bg_missing.exit_code == 1


def test_argo_namespace_never_names_the_kubeconfig_context(tmp_path: Path) -> None:
    """`--namespace` scopes the custom resources and never selects a kubeconfig context (#961).

    Each workflows and rollouts command used to pass its namespace to the CRD service as
    the context, so outside a pod `-n argocd` looked up a kubeconfig context named
    `argocd`: an error, or another cluster when a context of that name existed.
    """
    from devops_cli.k8s.service import KubernetesService

    succeeded = {
        "metadata": {"name": "my-wf", "namespace": "argocd"},
        "status": {"phase": "Succeeded", "nodes": {}},
    }
    crd_api = MagicMock()
    crd_api.list_namespaced_custom_object.return_value = {"items": []}
    crd_api.get_namespaced_custom_object.return_value = succeeded
    crd_api.create_namespaced_custom_object.return_value = succeeded
    contexts: list[str | None] = []

    def custom_objects_api(self: KubernetesService, context: str | None = None) -> MagicMock:
        contexts.append(context)
        return crd_api

    workflow = tmp_path / "wf.yaml"
    workflow.write_text(
        "apiVersion: argoproj.io/v1alpha1\nkind: Workflow\nmetadata:\n  name: my-wf\n",
        encoding="utf-8",
    )
    invocations = [
        ["workflows", "list", "--namespace", "argocd"],
        ["workflows", "submit", str(workflow), "--namespace", "argocd", "--wait"],
        ["workflows", "logs", "my-wf", "--namespace", "argocd"],
        ["rollouts", "list", "--namespace", "argocd"],
        ["rollouts", "status", "my-rollout", "--namespace", "argocd"],
    ]
    with (
        patch.object(KubernetesService, "custom_objects_api", custom_objects_api),
        patch.object(KubernetesService, "read_pod_logs", return_value=iter(())),
    ):
        exit_codes = [runner.invoke(argo_app, args).exit_code for args in invocations]

    namespaces = {call.kwargs["namespace"] for call in crd_api.method_calls}
    assert (exit_codes, set(contexts), namespaces) == ([0] * 5, {None}, {"argocd"})


def test_argo_cd_apps_list_and_status_dry_run() -> None:
    """Verify argo cd apps list and status in dry-run mode."""
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res_list = runner.invoke(argo_app, ["cd", "apps", "list"])
        assert res_list.exit_code == 0
        assert "Plan for listing Argo CD applications" in res_list.output
    finally:
        set_dry_run(False)


def test_argo_cd_apps_list_and_status_render(web: WebFake, local_argocd: str) -> None:
    """Verify live rendering for argo cd apps list and status."""
    app_data = {
        "metadata": {"name": "sample-app"},
        "spec": {
            "project": "default",
            "source": {"repoURL": "https://github.com/org/repo.git", "targetRevision": "main"},
        },
        "status": {
            "sync": {"status": "Synced", "revision": "abc1234"},
            "health": {"status": "Healthy"},
        },
    }
    _serve_argocd(web, {"items": [app_data]}, app_data)

    res_list = runner.invoke(argo_app, ["cd", "apps", "list"])
    assert res_list.exit_code == 0
    assert "sample-app" in res_list.output

    res_status = runner.invoke(argo_app, ["cd", "apps", "status", "sample-app"])
    assert res_status.exit_code == 0
    assert "sample-app" in res_status.output


def test_argo_cd_apps_list_shows_first_source_of_multi_source_app(
    web: WebFake, local_argocd: str
) -> None:
    """The Repo column shows the first source of an Application with `spec.sources` (#2579)."""
    single = {"metadata": {"name": "single-app"}, "spec": {"source": {"repoURL": SINGLE_REPO}}}
    multi = {
        "metadata": {"name": "multi-app"},
        "spec": {"sources": [{"repoURL": CHART_REPO}, {"repoURL": GIT_REPO, "ref": "values"}]},
    }
    _serve_argocd(web, {"items": [single, multi]}, single)

    result = runner.invoke(argo_app, ["cd", "apps", "list"], env={"COLUMNS": "250"})

    assert result.exit_code == 0
    assert SINGLE_REPO in result.output
    assert CHART_REPO in result.output
    assert GIT_REPO not in result.output


def test_argo_cd_apps_list_help_states_the_repo_rule() -> None:
    """The help of `apps list` states which source the Repo column shows (#2579)."""
    result = runner.invoke(argo_app, ["cd", "apps", "list", "--help"], env={"COLUMNS": "250"})

    assert result.exit_code == 0
    assert "Repo column shows the first source" in " ".join(result.output.split())


def test_argo_cd_apps_list_null_items(web: WebFake, local_argocd: str) -> None:
    """Verify argo cd apps list handles null items array when zero apps exist (#765)."""
    web.respond("GET", f"{local_argocd}/api/v1/applications", 200, {"metadata": {}, "items": None})

    res = runner.invoke(argo_app, ["cd", "apps", "list"])

    assert (res.exit_code, "ArgoCD Applications" in res.output) == (0, True)


def test_argo_rollout_state_from_manifest_safe_step() -> None:
    """Verify ArgoRolloutState.from_manifest safely coerces and parses currentStepIndex."""
    from devops_cli.models.argo import ArgoRolloutState

    manifest = {
        "metadata": {"name": "rollout-a", "namespace": "default"},
        "spec": {"replicas": 3, "strategy": {"canary": {"steps": [{"setWeight": 20}]}}},
        "status": {"currentStepIndex": "0", "phase": "Healthy"},
    }
    state = ArgoRolloutState.from_manifest(manifest)
    assert (state.name, state.current_step, state.total_steps) == ("rollout-a", 0, 1)

    # Invalid non-integer step index falls back to None
    manifest["status"]["currentStepIndex"] = "invalid"
    state_invalid = ArgoRolloutState.from_manifest(manifest)
    assert (state_invalid.current_step,) == (None,)


def _workflow(
    cluster: FakeCluster, *, annotations: dict[str, str] | None, node: dict[str, Any]
) -> None:
    """Make the fake cluster hold the workflow `my-wf` in `argocd`, with one pod node."""
    metadata: dict[str, Any] = {"name": "my-wf", "namespace": "argocd"}
    if annotations:
        metadata["annotations"] = annotations
    cluster.custom_objects.objects[("argoproj.io", "v1alpha1", "workflows")] = [
        {"metadata": metadata, "status": {"phase": "Succeeded", "nodes": {"node-pod-1": node}}}
    ]


_V1_NAMES = {"workflows.argoproj.io/pod-name-format": "v1"}


def test_argo_workflows_logs_without_follow(cluster: FakeCluster) -> None:
    """Verify argo workflows logs without --follow prints framed lines after pod header."""
    _workflow(cluster, annotations=_V1_NAMES, node={"type": "Pod"})
    cluster.core.answers["read_namespaced_pod_log"] = {("argocd", "node-pod-1"): [b"a\nb\n"]}

    res = runner.invoke(argo_app, ["workflows", "logs", "my-wf", "--namespace", "argocd"])

    assert (res.exit_code, res.stdout, cluster.core.calls[-1][1]["container"]) == (
        0,
        "── node-pod-1 ──\na\nb\n",
        "main",
    )


def test_argo_workflows_logs_with_custom_container(cluster: FakeCluster) -> None:
    """Verify argo workflows logs passes --container to pod log reader."""
    _workflow(cluster, annotations=_V1_NAMES, node={"type": "Pod"})
    cluster.core.answers["read_namespaced_pod_log"] = {("argocd", "node-pod-1"): [b"log output\n"]}

    res = runner.invoke(
        argo_app,
        ["workflows", "logs", "my-wf", "--namespace", "argocd", "--container", "wait"],
    )

    assert (res.exit_code, res.stdout, cluster.core.calls[-1][1]["container"]) == (
        0,
        "── node-pod-1 ──\nlog output\n",
        "wait",
    )


def test_argo_workflows_logs_falls_back_to_v1_on_404(cluster: FakeCluster) -> None:
    """Verify argo workflows logs falls back to v1 naming when v2 pod returns 404."""
    _workflow(
        cluster,
        annotations=None,
        node={
            "id": "node-pod-1",
            "name": "my-wf[0].step1",
            "templateName": "step1-tmpl",
            "type": "Pod",
            "phase": "Succeeded",
        },
    )
    cluster.core.answers["read_namespaced_pod_log"] = {
        ("argocd", "node-pod-1"): [b"fallback logs\n"]
    }

    res = runner.invoke(argo_app, ["workflows", "logs", "my-wf", "--namespace", "argocd"])

    assert (
        res.exit_code,
        res.stdout,
        [call[1]["name"] == "node-pod-1" for call in cluster.core.calls],
        cluster.core.calls[-1][1]["container"],
    ) == (0, "── node-pod-1 ──\nfallback logs\n", [False, True], "main")


def test_argo_workflows_logs_with_follow(cluster: FakeCluster) -> None:
    """Verify argo workflows logs with --follow prints framed lines across chunk boundaries."""
    _workflow(cluster, annotations=_V1_NAMES, node={"type": "Pod"})
    cluster.core.answers["read_namespaced_pod_log"] = {("argocd", "node-pod-1"): [b"a\nb", b"c\n"]}

    res = runner.invoke(
        argo_app, ["workflows", "logs", "my-wf", "--namespace", "argocd", "--follow"]
    )

    assert (res.exit_code, res.stdout, cluster.core.calls[-1][1]["container"]) == (
        0,
        "── node-pod-1 ──\na\nbc\n",
        "main",
    )


def test_cd_apps_sync_payload_structure(web: WebFake, local_argocd: str) -> None:
    """cd_apps_sync sends top-level prune and strategy.apply.force without a sync wrapper."""
    sync_url = f"{local_argocd}/api/v1/applications/guestbook/sync"
    web.respond("POST", sync_url, 200, {})

    res = runner.invoke(argo_app, ["cd", "apps", "sync", "guestbook", "--prune", "--force"])

    assert res.exit_code == 0
    [sent] = web.recorded
    assert (sent.method, sent.url, sent.json) == (
        "POST",
        sync_url,
        {"prune": True, "strategy": {"apply": {"force": True}}},
    )


_ARGOCD_COMMANDS = [["list"], ["sync", "web"], ["status", "web"]]


@pytest.mark.parametrize("command", _ARGOCD_COMMANDS, ids=["list", "sync", "status"])
def test_a_refused_address_in_the_argocd_token_mint_ends_the_command_with_the_cause(
    cli: Callable[..., Any], web: WebFake, dns: DnsFake, command: list[str]
) -> None:
    """Old vs new (#2424): a failed token mint ends the command with its cause and no traceback.

    With the admin password and no token, the command mints a token before its request. The
    connect of the mint refuses the private answer without the flag, and the mint fails with the
    refusal as its cause. Before, the mint error came out of the command with a traceback.
    """
    dns.add("example.com", "192.0.2.10")

    result = cli(
        "argo",
        "cd",
        "apps",
        *command,
        env={
            "DEVOPS_CLI_ARGOCD_URL": "http://example.com:8080",
            "DEVOPS_CLI_ARGOCD_PASSWORD": "admin-pw",
            "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK": "false",
        },
    )

    assert (
        result.exit_code,
        type(result.exception),
        "token mint" in result.output,
        "the loopback egress level refuses" in result.output,
        web.recorded,
    ) == (1, SystemExit, True, True, [])


@pytest.mark.parametrize("command", _ARGOCD_COMMANDS, ids=["list", "sync", "status"])
def test_a_k8s_address_in_the_argocd_url_stops_the_command_before_the_token_mint(
    cli: Callable[..., Any], web: WebFake, dns: DnsFake, command: list[str]
) -> None:
    """Old vs new (#2424): the URL check runs before the token mint, and it names the setting.

    Before, the command minted the token first, and the URL error of the mint came out of the
    command with a traceback.
    """

    result = cli(
        "argo",
        "cd",
        "apps",
        *command,
        env={
            "DEVOPS_CLI_ARGOCD_URL": "k8s://argocd/argocd-server:80",
            "DEVOPS_CLI_ARGOCD_PASSWORD": "admin-pw",
        },
    )

    assert (
        result.exit_code,
        type(result.exception),
        "argocd.url" in result.output,
        dns.lookups_of("argocd"),
        web.recorded,
    ) == (1, SystemExit, True, [], [])


_ARGOCD = "https://argocd.example.com"
_SYNC_PATH = "/api/v1/applications/web/sync"
_SESSION_PATH = "/api/v1/session"


def _refusing_argocd(web: WebFake, status: int = 401) -> list[tuple[str, str]]:
    """Serve an Argo CD that answers `status` to the stored token `stale` and accepts `fresh`.

    The session request gives the token `fresh`. Return the log of (path, bearer) pairs.
    """
    log: list[tuple[str, str]] = []
    application = {
        "metadata": {"name": "web"},
        "spec": {"project": "default", "source": {"repoURL": "https://example.com/repo.git"}},
        "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}},
    }

    def server(request: httpx2.Request) -> httpx2.Response:
        bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
        log.append((request.url.path, bearer))
        if request.url.path == _SESSION_PATH:
            return httpx2.Response(200, json={"token": "fresh"})
        if bearer != "fresh":
            return httpx2.Response(status, json={"error": "invalid session"})
        return httpx2.Response(200, json={"items": [application]})

    web.serve(server)
    return log


@pytest.fixture
def stale_argocd(config: Callable[..., Path], keyring_store: Any) -> Any:
    """Point devops-cli at a fake Argo CD with the stored token `stale`, and return the keyring."""
    config(argocd={"url": _ARGOCD})
    keyring_store.values["argocd_token"] = "stale"
    return keyring_store


def test_sync_replaces_a_refused_token_and_syncs(
    cli: Callable[..., Any], web: WebFake, stale_argocd: Any
) -> None:
    """Old vs new (#2576): a 401 with the admin password stored mints a token and syncs."""
    stale_argocd.values["argocd_password"] = "admin-pw"
    log = _refusing_argocd(web)

    result = cli("argo", "cd", "apps", "sync", "web")

    assert (result.exit_code, "Sync triggered for 'web'." in result.output) == (0, True)
    assert (stale_argocd.values["argocd_token"], log) == (
        "fresh",
        [(_SYNC_PATH, "stale"), (_SESSION_PATH, ""), (_SYNC_PATH, "fresh")],
    )


def test_sync_with_a_refused_token_and_no_password_tells_how_to_fix_it(
    cli: Callable[..., Any], web: WebFake, stale_argocd: Any
) -> None:
    """Old vs new (#2576): before, the 401 left the command as a traceback."""
    log = _refusing_argocd(web)

    result = cli("argo", "cd", "apps", "sync", "web")

    assert (
        result.exit_code,
        "argocd.token" in result.output,
        "sync-secrets" in result.output,
        type(result.exception),
        log,
    ) == (1, True, True, SystemExit, [(_SYNC_PATH, "stale")])


def test_sync_with_another_error_status_ends_with_the_status(
    cli: Callable[..., Any], web: WebFake, stale_argocd: Any
) -> None:
    """Old vs new (#2576): an HTTP 500 is one error line with its status, with no traceback."""
    stale_argocd.values["argocd_password"] = "admin-pw"
    log = _refusing_argocd(web, status=500)

    result = cli("argo", "cd", "apps", "sync", "web")

    assert (
        result.exit_code,
        "HTTP 500" in result.output,
        type(result.exception),
        log,
    ) == (1, True, SystemExit, [(_SYNC_PATH, "stale")])


def test_list_replaces_a_refused_token_and_shows_the_applications(
    cli: Callable[..., Any], web: WebFake, stale_argocd: Any
) -> None:
    """Old vs new (#2576): before, the list showed the 401 as its error row."""
    stale_argocd.values["argocd_password"] = "admin-pw"
    _refusing_argocd(web)

    result = cli("argo", "cd", "apps", "list")

    assert (result.exit_code, "web" in result.output, "Error" in result.output) == (0, True, False)
    assert stale_argocd.values["argocd_token"] == "fresh"


def test_list_with_a_refused_token_and_no_password_names_the_setting(
    cli: Callable[..., Any], web: WebFake, stale_argocd: Any
) -> None:
    """The error row of the list tells how to set the token; the list keeps its exit status 0."""
    _refusing_argocd(web)

    result = cli("argo", "cd", "apps", "list")

    assert (result.exit_code, "argocd.token" in result.output) == (0, True)
