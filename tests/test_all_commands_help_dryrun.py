"""Unit tests testing all devops CLI subcommand apps directly with --help and --dry-run flags."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ai import app as ai_app
from devops_cli.commands.argo import app as argo_app
from devops_cli.commands.ci import app as ci_app
from devops_cli.commands.config import app as config_app
from devops_cli.commands.k8s import app as k8s_app
from devops_cli.commands.mcp import app as mcp_app
from devops_cli.commands.repos import app as repos_app
from devops_cli.commands.ssh import app as ssh_app
from devops_cli.main import app as main_app

COMMAND_SPECS = [
    (main_app, ["--help"]),
    (main_app, ["--dry-run", "repos", "status"]),
    (main_app, ["--dry-run", "config", "show"]),
    (main_app, ["--dry-run", "repos", "status"]),
    (main_app, ["--dry-run", "k8s", "status"]),
    (main_app, ["--dry-run", "k8s", "port-forward"]),
    (main_app, ["--dry-run", "argo", "list"]),
    (main_app, ["--dry-run", "argo", "status"]),
    (ai_app, ["--help"]),
    (ai_app, ["config", "--help"]),
    (ai_app, ["test", "--help"]),
    (ai_app, ["review", "--help"]),
    (ai_app, ["pipeline", "--help"]),
    (config_app, ["--help"]),
    (config_app, ["output", "--help"]),
    (repos_app, ["--help"]),
    (repos_app, ["list", "--help"]),
    (ssh_app, ["--help"]),
    (ssh_app, ["status", "--help"]),
    (ssh_app, ["audit", "--help"]),
    (k8s_app, ["--help"]),
    (k8s_app, ["port-forward", "--help"]),
    (argo_app, ["--help"]),
    (mcp_app, ["--help"]),
    (mcp_app, ["tools", "--help"]),
    (ci_app, ["--help"]),
]


runner = CliRunner()


@pytest.mark.parametrize(
    ("app_instance", "args"),
    COMMAND_SPECS,
)
def test_subcommand_apps_help_and_dryrun(app_instance, args: list[str]) -> None:
    """Validate that every subcommand app accepts --help or --dry-run with exit code 0."""
    result = runner.invoke(app_instance, args)
    assert result.exit_code == 0, f"Command {' '.join(args)} failed with output:\n{result.output}"
