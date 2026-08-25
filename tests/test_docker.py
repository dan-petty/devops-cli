"""Unit tests for docker CLI commands (devops_cli.commands.docker)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.main import app as main_app

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["docker"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_docker_commands() -> None:
    """Verify docker stats, ps, images, and analyze-layers subcommands."""
    mock_stats = [
        {
            "Container": "devops-app",
            "CPUPerc": "1.2%",
            "MemUsage": "50MiB / 1GiB",
            "MemPerc": "5.0%",
        }
    ]
    lines = "\n".join(json.dumps(s) for s in mock_stats)
    with patch("devops_cli.core.process.run_subprocess", return_value=_mock_proc(0, lines)):
        res_stats = runner.invoke(main_app, ["--dry-run", "docker", "stats"])
        assert res_stats.exit_code == 0

        res_ps = runner.invoke(main_app, ["--dry-run", "docker", "ps"])
        assert res_ps.exit_code == 0

    mock_client = MagicMock()
    mock_img = MagicMock()
    mock_img.tags = ["alpine:latest"]
    mock_img.short_id = "sha256:1234"
    mock_img.attrs = {"Size": 5000000}
    mock_client.images.list.return_value = [mock_img]

    with patch("devops_cli.commands.docker._client", return_value=mock_client):
        res_images = runner.invoke(docker_app, ["images"])
        assert res_images.exit_code == 0

        res_analyze = runner.invoke(docker_app, ["analyze-layers", "--dry-run", "alpine:latest"])
        assert res_analyze.exit_code == 0
