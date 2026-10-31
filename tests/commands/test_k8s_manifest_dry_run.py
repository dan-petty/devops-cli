"""Tests for dry-run request plans and classifications across 18 Kubernetes manifest and kustomize commands.

Issue #2239: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s.bootstrap import bootstrap
from devops_cli.commands.k8s.cluster_context import (
    apply as k8s_apply,
)
from devops_cli.commands.k8s.cluster_context import (
    render as k8s_render,
)
from devops_cli.commands.k8s.diagnostics import (
    chaos_cmd,
    diff_helm_cmd,
)
from devops_cli.commands.k8s.mattermost_bootstrap import (
    bootstrap_mattermost,
)
from devops_cli.commands.k8s.networking import (
    configure_urls,
)
from devops_cli.commands.k8s.security_audit import (
    k8s_check_deprecated,
    k8s_lint,
    k8s_validate,
    validate_policy_cmd,
)
from devops_cli.commands.k8s.stack_lifecycle import (
    bootstrap_openwebui,
    sync_secrets,
    teardown_stack,
)
from devops_cli.commands.k8s.tls_management import (
    create_tls_secret,
    enable_tls_stack,
)
from devops_cli.commands.kustomize import (
    apply as kustomize_apply,
)
from devops_cli.commands.kustomize import (
    build as kustomize_build,
)
from devops_cli.commands.kustomize import (
    diff as kustomize_diff,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("k8s apply", k8s_apply, ["k8s", "apply", "k8s/base", "--dry-run"]),
    ("k8s bootstrap", bootstrap, ["k8s", "bootstrap", "--dry-run"]),
    (
        "k8s bootstrap-mattermost",
        bootstrap_mattermost,
        ["k8s", "bootstrap-mattermost", "--dry-run"],
    ),
    ("k8s bootstrap-openwebui", bootstrap_openwebui, ["k8s", "bootstrap-openwebui", "--dry-run"]),
    ("k8s chaos", chaos_cmd, ["k8s", "chaos", "--dry-run"]),
    ("k8s check-deprecated", k8s_check_deprecated, ["k8s", "check-deprecated", ".", "--dry-run"]),
    ("k8s configure-urls", configure_urls, ["k8s", "configure-urls", "--dry-run"]),
    (
        "k8s create-tls-secret",
        create_tls_secret,
        ["k8s", "create-tls-secret", "my-secret", "--dry-run"],
    ),
    ("k8s diff-helm", diff_helm_cmd, ["k8s", "diff-helm", "my-rel", ".", "--dry-run"]),
    ("k8s enable-tls", enable_tls_stack, ["k8s", "enable-tls", "--dry-run"]),
    ("k8s render", k8s_render, ["k8s", "render", "k8s/base", "--dry-run"]),
    ("k8s sync-secrets", sync_secrets, ["k8s", "sync-secrets", "--dry-run"]),
    ("k8s teardown-stack", teardown_stack, ["k8s", "teardown-stack", "--dry-run"]),
    ("k8s validate", k8s_validate, ["k8s", "validate", ".", "--dry-run"]),
    ("kustomize apply", kustomize_apply, ["kustomize", "apply", ".", "--dry-run"]),
    ("kustomize build", kustomize_build, ["kustomize", "build", ".", "--dry-run"]),
    ("kustomize diff", kustomize_diff, ["kustomize", "diff", ".", "--dry-run"]),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("k8s lint", k8s_lint, ["--dry-run", "k8s", "lint", "."]),
    ("k8s validate-policy", validate_policy_cmd, ["--dry-run", "k8s", "validate-policy", "."]),
]


@pytest.fixture
def block_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real subprocess, socket, or process executions occur during dry-run."""

    def _fail_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected process invocation: {args}, {kwargs}")

    def _fail_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected socket call: {args}, {kwargs}")

    monkeypatch.setattr(subprocess, "run", _fail_process)
    monkeypatch.setattr(subprocess, "Popen", _fail_process)
    monkeypatch.setattr("devops_cli.core.process.run_subprocess", _fail_process)
    monkeypatch.setattr(socket, "socket", _fail_socket)
    monkeypatch.setattr(socket, "create_connection", _fail_socket)


@pytest.mark.parametrize("cmd_name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_classified(cmd_name: str, callback: Any, argv: list[str]) -> None:
    """Verify that external-request commands carry request-plan dry-run class."""
    cls = get_dry_run_class(callback)
    assert cls == "request-plan", (
        f"Command '{cmd_name}' has dry-run class {cls!r}, expected 'request-plan'"
    )


@pytest.mark.parametrize("cmd_name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_classified(
    cmd_name: str, callback: Any, argv: list[str]
) -> None:
    """Verify that local commands carry no-external-request dry-run class."""
    cls = get_dry_run_class(callback)
    assert cls == "no-external-request", (
        f"Command '{cmd_name}' has dry-run class {cls!r}, expected 'no-external-request'"
    )


@pytest.mark.parametrize("cmd_name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_execute_offline(
    cmd_name: str, callback: Any, argv: list[str], block_external_calls: None
) -> None:
    """Executing --dry-run prints request plan and makes zero external requests."""
    res = runner.invoke(app, argv)
    assert res.exit_code == 0, f"Command {argv} failed with output:\n{res.output}"
    assert (
        "Planned requests" in res.output
        or "Planned" in res.output
        or "kubectl" in res.output
        or "minikube" in res.output
        or "pluto" in res.output
        or "helm" in res.output
        or "kustomize" in res.output
        or "kubeconform" in res.output
        or "dry_run" in res.output
        or "dry-run" in res.output
    ), f"Command {argv} did not render expected request plan output:\n{res.output}"


def test_plan_k8s_apply_variations() -> None:
    """plan_k8s_apply handles plain and templated manifest plans."""
    from devops_cli.k8s.manifest_plans import plan_k8s_apply

    p_plain = plan_k8s_apply("k8s/base/deploy.yaml", namespace="prod")
    assert p_plain[0].method == "kubectl"
    assert "apply" in p_plain[0].argv
    assert "--namespace" in p_plain[0].argv

    p_tpl = plan_k8s_apply("k8s/base/deploy.yaml", template=True, domain="example.com")
    assert p_tpl[0].stdin == "<rendered-manifest>"


def test_plan_k8s_render() -> None:
    """plan_k8s_render constructs kustomize build command."""
    from devops_cli.k8s.manifest_plans import plan_k8s_render

    plan = plan_k8s_render("k8s/overlays/prod")
    assert plan[0].target == "kustomize"


def test_plan_k8s_bootstrap() -> None:
    """plan_k8s_bootstrap includes minikube and stack deployments."""
    from devops_cli.k8s.manifest_plans import plan_k8s_bootstrap

    plans = plan_k8s_bootstrap(Path("k8s"), stack="infra", auto_start=True)
    assert any(p.method == "minikube" for p in plans)
    assert any("deploy-stack" in p.argv for p in plans)


def test_plan_k8s_bootstrap_openwebui() -> None:
    """plan_k8s_bootstrap_openwebui covers pod lookup and exec commands."""
    from devops_cli.k8s.manifest_plans import plan_k8s_bootstrap_openwebui

    plans = plan_k8s_bootstrap_openwebui("admin@example.com", "Admin", context="docker-desktop")
    assert len(plans) == 2
    assert plans[0].target == "pods"
    assert plans[1].target == "exec"


def test_plan_k8s_chaos() -> None:
    """plan_k8s_chaos covers pod retrieval, deletion, and rollout status."""
    from devops_cli.k8s.manifest_plans import plan_k8s_chaos

    plans = plan_k8s_chaos(
        experiment="pod-kill", deployment="api", namespace="staging", duration=15
    )
    assert len(plans) == 3
    assert plans[0].target == "pods"
    assert plans[1].target == "pod"
    assert plans[2].target == "deployment"


def test_plan_k8s_check_deprecated() -> None:
    """plan_k8s_check_deprecated covers pluto deprecation plan."""
    from devops_cli.k8s.manifest_plans import plan_k8s_check_deprecated

    plan = plan_k8s_check_deprecated("k8s/manifests")
    assert plan[0].method == "pluto"


def test_plan_k8s_configure_urls() -> None:
    """plan_k8s_configure_urls covers ingress and node-port plans."""
    from devops_cli.k8s.manifest_plans import plan_k8s_configure_urls

    p_ing = plan_k8s_configure_urls("infra", context="minikube")
    assert len(p_ing) == 1
    assert p_ing[0].target == "ingress"

    p_np = plan_k8s_configure_urls("infra", addressing="node-port")
    assert len(p_np) == 2
    assert p_np[1].target == "nodes"


def test_plan_k8s_create_tls_secret() -> None:
    """plan_k8s_create_tls_secret covers namespace and secret creation."""
    from devops_cli.k8s.manifest_plans import plan_k8s_create_tls_secret

    plans = plan_k8s_create_tls_secret("web-tls", "prod", "cert.pem", "key.pem", context="ctx")
    assert len(plans) == 2
    assert "namespace/prod" in plans[0].target
    assert "secret/web-tls" in plans[1].target


def test_plan_k8s_diff_helm() -> None:
    """plan_k8s_diff_helm covers helm diff invocation."""
    from devops_cli.k8s.manifest_plans import plan_k8s_diff_helm

    plan = plan_k8s_diff_helm("rel", "charts/app", namespace="prod", values=["values.yaml"])
    assert plan[0].method == "helm"


def test_plan_k8s_enable_tls() -> None:
    """plan_k8s_enable_tls covers namespaces across stacks."""
    from devops_cli.k8s.manifest_plans import plan_k8s_enable_tls

    plans = plan_k8s_enable_tls("infra", "/etc/ssl", "tls-sec", overwrite=True)
    assert any("argocd" in p.target for p in plans)


def test_plan_k8s_sync_secrets() -> None:
    """plan_k8s_sync_secrets covers secret query."""
    from devops_cli.k8s.manifest_plans import plan_k8s_sync_secrets

    plan = plan_k8s_sync_secrets("infra", context="ctx")
    assert "argocd-initial-admin-secret" in plan[0].target


def test_plan_k8s_teardown_stack() -> None:
    """plan_k8s_teardown_stack covers apps query and deletion."""
    from devops_cli.k8s.manifest_plans import plan_k8s_teardown_stack

    plans = plan_k8s_teardown_stack(Path("k8s"), stack="infra", context="ctx")
    assert len(plans) == 2


def test_plan_k8s_validate() -> None:
    """plan_k8s_validate covers kubeconform command."""
    from devops_cli.k8s.manifest_plans import plan_k8s_validate

    plan = plan_k8s_validate("deploy.yaml", k8s_version="1.31.0", strict=True)
    assert plan[0].method == "kubeconform"


def test_plan_kustomize_variations() -> None:
    """plan_kustomize covers apply, build, and diff invocations."""
    from devops_cli.k8s.manifest_plans import (
        plan_kustomize_apply,
        plan_kustomize_build,
        plan_kustomize_diff,
    )

    p_apply = plan_kustomize_apply(".", namespace="prod")
    assert p_apply[0].method == "kubectl"
    assert "-k" in p_apply[0].argv

    p_apply_tpl = plan_kustomize_apply(".", template=True)
    assert p_apply_tpl[0].stdin == "<rendered-manifest>"

    p_build = plan_kustomize_build(".", output="out.yaml")
    assert p_build[0].method == "kustomize"
    assert "--output" in p_build[0].argv

    p_diff = plan_kustomize_diff(".")
    assert p_diff[0].method == "kubectl"
    assert "diff" in p_diff[0].argv
