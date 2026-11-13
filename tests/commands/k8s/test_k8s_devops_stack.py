"""Tests for the Kubernetes devops stack lifecycle and inclusion in stack all."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.networking import VALID_STACKS, _resolve_stacks
from devops_cli.commands.k8s.stack_lifecycle import (
    MANIFESTS_BY_STACK,
    PRODUCT_MANIFESTS_BY_STACK,
)
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.process import ProcessFake
from tests.support.k8s_tree import TREE
from tests.support.paths import REPO_ROOT

runner = CliRunner()


# The GitHub App the Service acts as, in config.yaml (ADR 0015).
_GITHUB_APP = "  github_app:\n    app_id: 1001\n    installation_id: 42\n    slug: devops-roadmap\n"


def test_devops_stack_registration_and_resolution() -> None:
    """Verify devops stack is registered and resolved in stack all and stack devops."""
    assert (
        "devops" in VALID_STACKS,
        _resolve_stacks("devops"),
        _resolve_stacks("all"),
    ) == (
        True,
        ["devops"],
        ["infra", "llm", "logging", "devops", "gitea", "chat"],
    )


def test_devops_stack_manifests_integrity() -> None:
    """Every devops manifest exists: the product paths under the product base `k8s/devops`, then
    the environment paths (#5131). The ConfigMap is rendered from config at deploy time instead.
    The rate limit of the webhook route is applied before the Ingress that names it (#2476)."""
    manifests = [
        *(TREE.path("devops") / p for p in PRODUCT_MANIFESTS_BY_STACK["devops"]),
        *(TREE.path(p) for p in MANIFESTS_BY_STACK["devops"]),
    ]
    filenames = [p.name for p in manifests]
    rate_limit_then_ingress = ["roadmap-service/middleware.yaml", "roadmap-service/ingress.yaml"]

    assert (
        len(manifests),
        all(p.exists() for p in manifests),
        "networkpolicy.yaml" in filenames,
        "serviceaccount.yaml" in filenames,
        any(p.parent.name == "devops" and p.name == "configmap.yaml" for p in manifests),
        "cronjob.yaml" in filenames,
        "deployment.yaml" in filenames,
        "service.yaml" in filenames,
        "clusterrolebinding.yaml" in filenames,
        sorted(
            f"{p.parent.name}/{p.name}"
            for p in manifests
            if p.name
            in {
                "cronjob-runner.yaml",
                "cronjob-stage.yaml",
                "role.yaml",
                "networkpolicy-egress.yaml",
            }
        ),
        [
            f"{p.parent.name}/{p.name}"
            for p in manifests
            if f"{p.parent.name}/{p.name}" in rate_limit_then_ingress
        ],
    ) == (
        31,
        True,
        True,
        True,
        False,
        True,
        True,
        True,
        True,
        [
            "devops/cronjob-runner.yaml",
            "devops/cronjob-stage.yaml",
            "roadmap-service/networkpolicy-egress.yaml",
            "roadmap-service/role.yaml",
        ],
        rate_limit_then_ingress,
    )


def test_devops_namespace_in_namespaces_yaml() -> None:
    """Verify namespace devops is registered in k8s/namespaces.yaml."""
    docs = list(
        yaml.safe_load_all((REPO_ROOT / "k8s" / "namespaces.yaml").read_text(encoding="utf-8"))
    )
    names = {d["metadata"]["name"] for d in docs if d and d.get("kind") == "Namespace"}

    assert "devops" in names


def test_deploy_stack_devops_dry_run(isolate_devops_cli_config: Path) -> None:
    """Verify deploy-stack --stack devops includes devops manifests in dry-run output."""
    from devops_cli.config.settings import reset_settings_cache

    with isolate_devops_cli_config.open("a", encoding="utf-8") as config:
        config.write("service:\n  repos:\n    - owner/repo\n" + _GITHUB_APP)
    reset_settings_cache()
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "devops"])
        assert (
            result.exit_code,
            "devops/configmap.yaml" in result.output,
            "roadmap-service" in result.output,
            "cronjob.yaml" in result.output,
            "searxng/configmap.yaml" in result.output,
        ) == (0, False, True, True, True)
    finally:
        set_dry_run(False)


def test_roadmap_service_ingress_uses_prefix_pathtype() -> None:
    """Verify roadmap-service ingress uses Prefix pathType for robust routing."""
    ingress_file = REPO_ROOT / "k8s" / "devops" / "roadmap-service" / "ingress.yaml"
    data = yaml.safe_load(ingress_file.read_text(encoding="utf-8"))
    rule = data["spec"]["rules"][0]
    path_entry = rule["http"]["paths"][0]

    assert (
        rule["host"],
        path_entry["path"],
        path_entry["pathType"],
        path_entry["backend"]["service"]["name"],
        path_entry["backend"]["service"]["port"]["number"],
    ) == (
        "hooks.example.com",
        "/webhooks/github",
        "Prefix",
        "roadmap-service",
        8000,
    )


def test_the_ingress_routes_hold_no_ingress_of_the_devops_namespace() -> None:
    """The Ingress `devops/roadmap-service` is product content: only
    `k8s/devops/roadmap-service/ingress.yaml` holds it, and the environment routes of
    `k8s/ingress/ingress-routes.yaml` hold no copy (#5292)."""
    routes_file = REPO_ROOT / "k8s" / "ingress" / "ingress-routes.yaml"
    docs = list(yaml.safe_load_all(routes_file.read_text(encoding="utf-8")))

    assert [
        d["metadata"]["name"]
        for d in docs
        if d and d.get("kind") == "Ingress" and d["metadata"].get("namespace") == "devops"
    ] == []


def test_deploy_stack_domain_option_in_dry_run(isolate_devops_cli_config: Path) -> None:
    """Verify deploy-stack propagates domain option in dry-run output."""
    from devops_cli.config.settings import reset_settings_cache

    with isolate_devops_cli_config.open("a", encoding="utf-8") as config:
        config.write("service:\n  repos:\n    - owner/repo\n" + _GITHUB_APP)
    reset_settings_cache()
    set_dry_run(True)
    try:
        result = runner.invoke(
            app, ["deploy-stack", "--stack", "devops", "--domain", "example.com"]
        )
        assert (
            result.exit_code,
            "example.com" in result.output,
        ) == (0, True)
    finally:
        set_dry_run(False)


def test_apply_single_manifest_renders_domain_template(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Verify _apply_single_manifest renders domain placeholders via stdin."""
    from devops_cli.commands.k8s.stack_lifecycle import _apply_single_manifest

    manifest = tmp_path / "test-ingress.yaml"
    manifest.write_text("host: hooks.${DOMAIN}\npath: /test\n", encoding="utf-8")

    _apply_single_manifest(str(manifest), ["--context", "test-ctx"], domain="example.com")

    assert [(call.argv, call.stdin, call.check) for call in process_fake.calls] == [
        (
            ("kubectl", "apply", "-f", "-", "--context", "test-ctx"),
            "host: hooks.example.com\npath: /test\n",
            False,
        )
    ]
