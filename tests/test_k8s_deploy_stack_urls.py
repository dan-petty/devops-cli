"""Tests verifying deploy-stack configures service URLs only when unconfigured (#1165)."""

from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from devops_cli.main import app

runner = CliRunner()


def _dry_run_details(output: str) -> dict[str, Any]:
    return json.loads(output[output.index("{") :])["details"]


def test_deploy_stack_dry_run_lists_config_writes_when_settings_empty(
    isolate_devops_cli_config: Any,
) -> None:
    """deploy-stack --dry-run lists config writes for deployed service URLs whose settings are empty."""
    isolate_devops_cli_config.write_text(
        "k8s:\n"
        "  context: minikube\n"
        "service:\n"
        "  repos:\n"
        "    - owner/repo\n"
        "  github_app:\n"
        "    app_id: 1001\n"
        "    installation_id: 42\n"
        "    slug: devops-roadmap\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["k8s", "deploy-stack", "--stack", "all", "--dry-run"])
    assert result.exit_code == 0
    details = _dry_run_details(result.output)
    assert "config_writes" in details
    writes = details["config_writes"]
    # Empty settings should be listed for configuration
    assert any("ai.gateway_url" in w for w in writes)
    assert any("qdrant.url" in w for w in writes)
    assert any("tempo.url" in w for w in writes)


def test_deploy_stack_dry_run_does_not_overwrite_configured_urls(
    isolate_devops_cli_config: Any,
) -> None:
    """deploy-stack --dry-run does not write settings that already have values."""
    isolate_devops_cli_config.write_text(
        "k8s:\n"
        "  context: minikube\n"
        "service:\n"
        "  repos:\n"
        "    - owner/repo\n"
        "  github_app:\n"
        "    app_id: 1001\n"
        "    installation_id: 42\n"
        "    slug: devops-roadmap\n"
        "ai:\n"
        "  gateway_url: https://custom-ai.example.com/v1\n"
        "qdrant:\n"
        "  url: https://custom-qdrant.example.com:6333\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["k8s", "deploy-stack", "--stack", "all", "--dry-run"])
    assert result.exit_code == 0
    details = _dry_run_details(result.output)
    writes = details["config_writes"]
    # Configured settings must not be overwritten
    assert not any("ai.gateway_url" in w for w in writes)
    assert not any("qdrant.url" in w for w in writes)
