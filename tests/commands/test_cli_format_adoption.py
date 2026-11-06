"""Tests verifying CLI output format adoption across the command surface."""

from __future__ import annotations

from typing import Any, Final

import click

from devops_cli.core.command_resolver import module_click_command
from devops_cli.docs.generator import DocGenerator

CONST_CLI_VALUE_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "ai ast graph",
        "ai ast parse",
        "ai audit-library-usage",
        "ai benchmark",
        "ai cache status",
        "ai chaos-model",
        "ai constellation",
        "ai cost list-pricing",
        "ai cost payback",
        "ai cost payoff",
        "ai cost report",
        "ai cost roi",
        "ai diagram",
        "ai failover",
        "ai gateway failover",
        "ai gateway load",
        "ai gateway probe-backend",
        "ai gateway routes",
        "ai gateway status",
        "ai gateway tune",
        "ai harness offload",
        "ai harness run",
        "ai harness status",
        "ai ingest docs",
        "ai ingest index-libraries",
        "ai ingest library",
        "ai ingest query-library",
        "ai pack-context",
        "ai prewarm",
        "ai prompt-eval",
        "ai quiesce",
        "ai rag drift",
        "ai read",
        "ai repomap",
        "ai research analogies",
        "ai research annotate",
        "ai research forage",
        "ai research model",
        "ai research socratic",
        "ai resume",
        "ai review corpus score",
        "ai review score",
        "ai review templates check",
        "ai review templates list",
        "ai review templates sweep",
        "ai runs baseline list",
        "ai runs baseline show",
        "ai runs check",
        "ai runs compare",
        "ai runs list",
        "ai runs show",
        "ai spec",
        "ai spend list-pricing",
        "ai spend payback",
        "ai spend payoff",
        "ai spend report",
        "ai spend roi",
        "ai test-gen",
        "ai token-count",
        "argo cd fleet sync",
        "argo cd gitops drift",
        "argo cd gitops sync",
        "argo cd gitops watch",
        "argo fleet sync",
        "argo gitops drift",
        "argo gitops sync",
        "argo gitops watch",
        "argo rollouts analyze",
        "argo sync",
        "cloudflare access policies",
        "cloudflare access status",
        "cloudflare access sync",
        "cloudflare dns delete",
        "cloudflare dns list",
        "cloudflare dns sync",
        "cloudflare service-status",
        "cloudflare status",
        "cloudflare tunnel routes",
        "cloudflare tunnel sync",
        "config audit-keys",
        "config env",
        "config env-vars",
        "config output",
        "docker cache",
        "docs generate",
        "gh branch-protection audit",
        "gh metrics",
        "gh pr hardening-report",
        "gh pr monitor",
        "gh pr threads list",
        "gh pr wait",
        "gh project workflows list",
        "gh rate-limit",
        "gh rate_limit",
        "gh runs list",
        "gh status",
        "grafana dashboards lint",
        "k8s chaos",
        "k8s doctor",
        "k8s gpu-matrix",
        "k8s logs",
        "k8s security-stream",
        "k8s service-url",
        "k8s validate",
        "k8s validate-policy",
        "pr hardening-report",
        "pr monitor",
        "pr threads list",
        "pr wait",
        "prometheus analyze",
        "repos worktrees prune",
        "repos worktrees status",
        "review corpus score",
        "review score",
        "review templates check",
        "review templates list",
        "review templates sweep",
        "sandbox logs",
        "sandbox metrics",
        "sandbox probe",
        "sandbox status",
        "sandbox traces",
        "scan aibom",
        "scan complexity",
        "scan report",
        "scan sarif",
        "scan sast",
        "scan sbom",
        "scan secrets",
        "scan trivy",
        "status",
        "telemetry logfire",
        "telemetry profile",
        "test profile-memory",
        "tf cost breakdown",
        "tf cost diff",
        "tf drift",
        "tf graph",
        "tf lint",
        "tf notify-plan",
        "tf output",
        "vault audit",
    }
)


def _extract_leaf_commands(cmd: Any, prefix: str) -> dict[str, Any]:
    """Recursively collect leaf commands from a Click command or group, hidden ones included."""
    leaves: dict[str, Any] = {}
    subcommands = getattr(cmd, "commands", None)
    if subcommands:
        for sub_name, subcmd in subcommands.items():
            child_prefix = f"{prefix} {sub_name}".strip()
            leaves.update(_extract_leaf_commands(subcmd, child_prefix))
    else:
        leaves[prefix] = cmd
    return leaves


def _collect_all_cli_leaf_commands() -> dict[str, Any]:
    """Walk the Click command of each documented command group and collect the leaf commands."""
    all_leaves: dict[str, Any] = {}
    for group in DocGenerator().introspect_all_groups():
        click_cmd = module_click_command(group.module_path)
        all_leaves.update(_extract_leaf_commands(click_cmd, group.name))
    return all_leaves


def _command_has_format_option(cmd: Any) -> bool:
    """Check if a Click command has a --format option."""
    return any("--format" in getattr(p, "opts", []) for p in cmd.params)


def test_every_value_command_exposes_format_option() -> None:
    """Every command classified as a value command must expose a --format option."""
    leaf_commands = _collect_all_cli_leaf_commands()

    missing_commands = [
        cmd_path
        for cmd_path in sorted(CONST_CLI_VALUE_COMMANDS)
        if cmd_path not in leaf_commands or not _command_has_format_option(leaf_commands[cmd_path])
    ]

    assert missing_commands == []


def test_negative_control_detects_missing_format_option() -> None:
    """Negative control ensuring omission of --format from a value command is detected."""
    dummy_cmd = click.Command("dummy", params=[click.Option(["--json", "-j"], is_flag=True)])
    assert _command_has_format_option(dummy_cmd) is False


def test_value_commands_registry_is_non_empty_and_sorted() -> None:
    """Verify CONST_CLI_VALUE_COMMANDS invariant: 142 registered value commands."""
    assert isinstance(CONST_CLI_VALUE_COMMANDS, frozenset)
    assert len(CONST_CLI_VALUE_COMMANDS) == 142
