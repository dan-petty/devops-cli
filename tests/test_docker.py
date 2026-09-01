"""Unit tests for docker CLI commands (devops_cli.commands.docker)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.security.dive import DiveAnalysisResult, DiveLayerInfo

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


def test_docker_commands(tmp_path: Path) -> None:
    """Verify docker images, build, push, prune, and analyze-layers subcommands."""
    mock_client = MagicMock()
    mock_img = MagicMock()
    mock_img.tags = ["alpine:latest"]
    mock_img.short_id = "sha256:1234"
    mock_img.attrs = {"Size": 5000000}
    mock_client.images.list.return_value = [mock_img]
    mock_client.images.build.return_value = (mock_img, [{"stream": "Step 1/1 : FROM alpine\n"}])
    mock_client.images.push.return_value = [{"status": "Pushing layer 1"}]
    mock_client.system.prune.return_value = {"SpaceReclaimed": 10485760}

    with patch("devops_cli.commands.docker._client", return_value=mock_client):
        res_images = runner.invoke(docker_app, ["images"])
        assert res_images.exit_code == 0

        res_images_dry = runner.invoke(docker_app, ["images", "--name", "alpine"])
        assert res_images_dry.exit_code == 0

        res_build = runner.invoke(docker_app, ["build", str(tmp_path), "--tag", "test:1.0"])
        assert res_build.exit_code == 0

        res_push = runner.invoke(docker_app, ["push", "test:1.0"])
        assert res_push.exit_code == 0

        res_prune = runner.invoke(docker_app, ["prune", "--force"])
        assert res_prune.exit_code == 0


def test_docker_stats_dry_run() -> None:
    """Verify docker stats --dry-run outputs the plan without touching Docker."""
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res = runner.invoke(docker_app, ["stats", "--name", "myapp", "--interval", "1.5"])
        assert res.exit_code == 0
        assert "docker_container_stats" in res.output
    finally:
        set_dry_run(False)


def test_docker_stats_sdk_table() -> None:
    """Verify docker stats table is built from Docker SDK container data."""
    from devops_cli.commands.docker import _build_docker_stats_table, _format_bytes

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = "web"
    mock_container.stats.return_value = {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 200_000_000, "percpu_usage": [100_000_000, 100_000_000]},
            "system_cpu_usage": 2_000_000_000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100_000_000},
            "system_cpu_usage": 1_000_000_000,
        },
        "memory_stats": {
            "usage": 52_428_800,
            "limit": 1_073_741_824,
            "stats": {"cache": 0},
        },
        "networks": {"eth0": {"rx_bytes": 1_024, "tx_bytes": 512}},
    }
    mock_client.containers.list.return_value = [mock_container]

    with patch("devops_cli.commands.docker._client", return_value=mock_client):
        table = _build_docker_stats_table(None)

    assert table.row_count == 1
    # _format_bytes sanity checks
    assert _format_bytes(0) == "0.0 B"
    assert _format_bytes(2048) == "2.0 KB"
    assert _format_bytes(5_242_880) == "5.0 MB"


def test_docker_analyze_layers() -> None:
    """Test docker analyze-layers subcommand."""
    mock_result = DiveAnalysisResult(
        image_name="alpine:latest",
        efficiency_score=0.98,
        total_bytes=5000000,
        wasted_bytes=100000,
        layers=[
            DiveLayerInfo(
                index=0,
                digest="sha256:1111",
                size_bytes=5000000,
                wasted_bytes=100000,
                command="FROM alpine",
            )
        ],
    )
    with patch("devops_cli.security.dive.run_dive_analysis", return_value=mock_result):
        res_table = runner.invoke(docker_app, ["analyze-layers", "alpine:latest"])
        assert res_table.exit_code == 0

        res_json = runner.invoke(docker_app, ["analyze-layers", "alpine:latest", "--json"])
        assert res_json.exit_code == 0
        assert "efficiency_score" in res_json.output

        res_dry = runner.invoke(docker_app, ["analyze-layers", "alpine:latest", "--dry-run"])
        assert res_dry.exit_code == 0


def test_docker_client_and_error_branches(tmp_path: Path) -> None:
    """Verify docker _client connection, push errors, and dry-run branches."""
    from devops_cli.commands.docker import _client
    from devops_cli.dry_run import set_dry_run

    # 1. _client connection failure
    with patch("docker.from_env", side_effect=Exception("Daemon not running")):
        with pytest.raises(Exception):
            _client()

    # 2. _client with DOCKER_HOST validation
    with (
        patch.dict("os.environ", {"DOCKER_HOST": "tcp://localhost:2375"}),
        patch("devops_cli.core.validation.validate_service_url"),
        patch("docker.from_env") as mock_env,
    ):
        _client()
        mock_env.assert_called_once()

    # 3. Dry run branches for build, push, prune, images
    set_dry_run(True)
    try:
        res_b_dry = runner.invoke(
            docker_app,
            ["build", str(tmp_path), "--file", str(tmp_path / "Dockerfile"), "--no-cache"],
        )
        assert res_b_dry.exit_code == 0
        assert "build_docker_image" in res_b_dry.output

        res_p_dry = runner.invoke(docker_app, ["push", "myimage:latest"])
        assert res_p_dry.exit_code == 0
        assert "push_docker_image" in res_p_dry.output

        res_pr_dry = runner.invoke(docker_app, ["prune"])
        assert res_pr_dry.exit_code == 0
        assert "prune_docker_resources" in res_pr_dry.output

        res_img_dry = runner.invoke(docker_app, ["images"])
        assert res_img_dry.exit_code == 0
        assert "list_docker_images" in res_img_dry.output
    finally:
        set_dry_run(False)

    # 4. Push invalid image name
    res_bad_img = runner.invoke(docker_app, ["push", "Invalid Name!"])
    assert res_bad_img.exit_code == 1

    # 5. Push stream error
    mock_client = MagicMock()
    mock_client.images.push.return_value = [{"error": "denied: access forbidden"}]
    with patch("devops_cli.commands.docker._client", return_value=mock_client):
        res_push_err = runner.invoke(docker_app, ["push", "org/repo:tag"])
        assert res_push_err.exit_code == 1
        assert "access forbidden" in res_push_err.output

    # 6. Prune with tuple return value and without force
    mock_client.system.prune.return_value = (None, {"containers": 5242880, "images": 5242880})
    with patch("devops_cli.commands.docker._client", return_value=mock_client):
        with patch("typer.confirm", return_value=True):
            res_prune_tuple = runner.invoke(docker_app, ["prune"])
            assert res_prune_tuple.exit_code == 0
            assert "10 MB" in res_prune_tuple.output


def test_docker_images_and_build_formatting(tmp_path: Path) -> None:
    """Verify docker images tag formatting and build stream logging."""
    mock_client = MagicMock()
    mock_img_unnamed = MagicMock()
    mock_img_unnamed.tags = []
    mock_img_unnamed.short_id = "sha256:5678"
    mock_img_unnamed.attrs = {"Size": 10485760}

    mock_client.images.list.return_value = [mock_img_unnamed]
    mock_client.images.build.return_value = (mock_img_unnamed, [{"stream": "Step 1 : Building\n"}])

    with patch("devops_cli.commands.docker._client", return_value=mock_client):
        res_images = runner.invoke(docker_app, ["images"])
        assert res_images.exit_code == 0
        assert "<none>" in res_images.output

        res_build = runner.invoke(docker_app, ["build", str(tmp_path)])
        assert res_build.exit_code == 0
        assert "Successfully built image" in res_build.output or "sha256:5678" in res_build.output
