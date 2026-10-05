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
