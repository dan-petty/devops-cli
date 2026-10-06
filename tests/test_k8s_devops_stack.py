"""Tests for the Kubernetes devops stack lifecycle and inclusion in stack all."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.networking import VALID_STACKS as NET_VALID_STACKS
from devops_cli.commands.k8s.networking import _resolve_stacks
from devops_cli.commands.k8s.stack_lifecycle import (
    _MANIFESTS_BY_STACK,
)
from devops_cli.commands.k8s.stack_lifecycle import (
    VALID_STACKS as LIFE_VALID_STACKS,
)
from devops_cli.dry_run import set_dry_run

runner = CliRunner()


def test_devops_stack_registration_and_resolution() -> None:
    """Verify devops stack is registered and resolved in stack all and stack devops."""
    assert (
        "devops" in NET_VALID_STACKS,
        "devops" in LIFE_VALID_STACKS,
        _resolve_stacks("devops"),
        _resolve_stacks("all"),
    ) == (
        True,
        True,
        ["devops"],
        ["infra", "llm", "logging", "devops"],
    )


def test_devops_stack_manifests_integrity() -> None:
    """Verify all manifests for the devops stack exist and cover core components."""
    from devops_cli.k8s.configmap import ensure_devops_configmap

    ensure_devops_configmap()
    manifests = _MANIFESTS_BY_STACK.get("devops", [])
    filenames = [p.name for p in manifests]

    assert (
        len(manifests),
        all(p.exists() for p in manifests),
        "networkpolicy.yaml" in filenames,
        "serviceaccount.yaml" in filenames,
        "configmap.yaml" in filenames,
        "cronjob.yaml" in filenames,
        "deployment.yaml" in filenames,
        "service.yaml" in filenames,
    ) == (
        9,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    )


def test_devops_namespace_in_namespaces_yaml() -> None:
    """Verify namespace devops is registered in k8s/namespaces.yaml."""
    repo_root = Path(__file__).resolve().parent.parent
    docs = list(
        yaml.safe_load_all((repo_root / "k8s" / "namespaces.yaml").read_text(encoding="utf-8"))
    )
    names = {d["metadata"]["name"] for d in docs if d and d.get("kind") == "Namespace"}

    assert "devops" in names


def test_deploy_stack_devops_dry_run() -> None:
    """Verify deploy-stack --stack devops includes devops manifests in dry-run output."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "devops"])
        assert (
            result.exit_code,
            "configmap.yaml" in result.output,
            "roadmap-service" in result.output,
            "cronjob.yaml" in result.output,
        ) == (0, True, True, True)
    finally:
        set_dry_run(False)


def test_roadmap_service_ingress_uses_prefix_pathtype() -> None:
    """Verify roadmap-service ingress uses Prefix pathType for robust routing."""
    repo_root = Path(__file__).resolve().parent.parent
    ingress_file = repo_root / "k8s" / "devops" / "roadmap-service" / "ingress.yaml"
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


def test_roadmap_service_ingress_in_ingress_routes() -> None:
    """Verify roadmap-service ingress is registered in k8s/ingress/ingress-routes.yaml."""
    repo_root = Path(__file__).resolve().parent.parent
    routes_file = repo_root / "k8s" / "ingress" / "ingress-routes.yaml"
    docs = list(yaml.safe_load_all(routes_file.read_text(encoding="utf-8")))
    roadmap_docs = [
        d
        for d in docs
        if d
        and d.get("kind") == "Ingress"
        and d.get("metadata", {}).get("name") == "roadmap-service"
    ]

    assert len(roadmap_docs) == 1
    spec = roadmap_docs[0]["spec"]
    assert (
        roadmap_docs[0]["metadata"]["namespace"],
        spec["rules"][0]["host"],
        spec["rules"][0]["http"]["paths"][0]["pathType"],
    ) == (
        "devops",
        "hooks.example.com",
        "Prefix",
    )


def test_deploy_stack_domain_option_in_dry_run() -> None:
    """Verify deploy-stack propagates domain option in dry-run output."""
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


def test_apply_single_manifest_renders_domain_template(tmp_path: Path) -> None:
    """Verify _apply_single_manifest renders domain placeholders via stdin."""
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.k8s.stack_lifecycle import _apply_single_manifest

    manifest = tmp_path / "test-ingress.yaml"
    manifest.write_text("host: hooks.${DOMAIN}\npath: /test\n", encoding="utf-8")

    mock_run = MagicMock()
    with patch("devops_cli.commands.k8s.stack_lifecycle.runtime._run_cmd", mock_run):
        _apply_single_manifest(str(manifest), ["--context", "test-ctx"], domain="example.com")

    assert mock_run.call_count == 1
    args, kwargs = mock_run.call_args
    assert (
        args[0],
        kwargs.get("input"),
        kwargs.get("check"),
    ) == (
        ["kubectl", "apply", "-f", "-", "--context", "test-ctx"],
        "host: hooks.example.com\npath: /test\n",
        False,
    )
