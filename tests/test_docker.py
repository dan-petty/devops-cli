"""Unit tests for docker CLI commands (devops_cli.commands.docker)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
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


def test_docker_commands(tmp_path: Path, docker_engine: Any) -> None:
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

    with docker_engine(mock_client):
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


def test_docker_stats_sdk_table(docker_engine: Any) -> None:
    """Verify docker stats table is built from typed Engine API container samples."""
    from devops_cli.commands.docker import _build_docker_stats_table, _format_bytes

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = "web"
    mock_container.attrs = {
        "Id": "c0ffee",
        "Name": "/web",
        "State": {"Status": "running", "Running": True},
        "Config": {"Image": "nginx:latest"},
    }
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
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client):
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
        status="ran",
        efficiency_score=0.98,
        total_bytes=5000000,
        wasted_bytes=100000,
        layers=[
            DiveLayerInfo(index=0, digest="sha256:1111", size_bytes=5000000, command="FROM alpine")
        ],
    )
    with patch("devops_cli.security.dive.run_dive_analysis", return_value=mock_result):
        res_table = runner.invoke(docker_app, ["analyze-layers", "alpine:latest"])
        assert res_table.exit_code == 0

        res_json = runner.invoke(docker_app, ["analyze-layers", "alpine:latest", "--json"])
        assert res_json.exit_code == 0
        assert json.loads(res_json.stdout)["efficiency_score"] == 0.98

        res_dry = runner.invoke(docker_app, ["analyze-layers", "alpine:latest", "--dry-run"])
        assert res_dry.exit_code == 0


def test_docker_analyze_layers_without_dive_says_so_and_fails() -> None:
    """With dive missing there is no table or score to show: a warning and a non-zero exit."""
    with patch("shutil.which", return_value=None):
        res_table = runner.invoke(docker_app, ["analyze-layers", "img:1"])
        res_json = runner.invoke(docker_app, ["analyze-layers", "img:1", "--json"])

    assert (res_table.exit_code, res_json.exit_code) == (1, 1)
    assert ("unavailable" in res_table.output, "Efficiency" in res_table.output) == (True, False)
    # stdout under --json is the JSON document alone.
    assert json.loads(res_json.stdout)["status"] == "unavailable"


def test_docker_analyze_layers_shows_layer_commands_as_text() -> None:
    """A layer command is image history, written by whoever built the image: its brackets are
    text, never Rich markup that drops words or adds styles and links."""
    commands = [
        "RUN pip install uvicorn[standard]",
        "FROM [bold]x[/bold] [link=https://x.test]y[/link]",
    ]
    analysis = DiveAnalysisResult(
        image_name="img:1",
        status="ran",
        layers=[DiveLayerInfo(index=i, command=c) for i, c in enumerate(commands)],
    )
    with patch("devops_cli.security.dive.run_dive_analysis", return_value=analysis):
        res = runner.invoke(docker_app, ["analyze-layers", "img:1"], env={"COLUMNS": "120"})

    assert (res.exit_code, [command in res.output for command in commands]) == (0, [True, True])


def test_docker_client_and_error_branches(tmp_path: Path, docker_engine: Any) -> None:
    """Verify docker _client connection, push errors, and dry-run branches."""
    from devops_cli.commands.docker import _engine
    from devops_cli.dry_run import set_dry_run

    # 1. An unreachable daemon is surfaced as a clean CLI exit rather than a traceback.
    with patch("docker.from_env", side_effect=Exception("Daemon not running")):
        with pytest.raises(typer.Exit):
            _engine()

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
    with docker_engine(mock_client):
        res_push_err = runner.invoke(docker_app, ["push", "org/repo:tag"])
        assert res_push_err.exit_code == 1
        assert "access forbidden" in res_push_err.output

    # 6. Prune with tuple return value and without force
    mock_client.system.prune.return_value = (None, {"containers": 5242880, "images": 5242880})
    with docker_engine(mock_client):
        with patch("typer.confirm", return_value=True):
            res_prune_tuple = runner.invoke(docker_app, ["prune"])
            assert res_prune_tuple.exit_code == 0
            assert "10 MB" in res_prune_tuple.output


def test_docker_images_and_build_formatting(tmp_path: Path, docker_engine: Any) -> None:
    """Verify docker images tag formatting and build stream logging."""
    mock_client = MagicMock()
    mock_img_unnamed = MagicMock()
    mock_img_unnamed.tags = []
    mock_img_unnamed.short_id = "sha256:5678"
    mock_img_unnamed.attrs = {"Size": 10485760}

    mock_client.images.list.return_value = [mock_img_unnamed]
    mock_client.images.build.return_value = (mock_img_unnamed, [{"stream": "Step 1 : Building\n"}])

    with docker_engine(mock_client):
        res_images = runner.invoke(docker_app, ["images"])
        assert res_images.exit_code == 0
        assert "<none>" in res_images.output

        res_build = runner.invoke(docker_app, ["build", str(tmp_path)])
        assert res_build.exit_code == 0
        assert "Successfully built image" in res_build.output or "sha256:5678" in res_build.output


def test_docker_push_registry_error_prints_as_written_and_exits_1(docker_engine: Any) -> None:
    """A push error is the registry's text: `[/v2/repo]` in it is text, not a Rich closing tag
    that ends the command in a MarkupError traceback instead of a clean exit 1 (#955)."""
    mock_client = MagicMock()
    mock_client.images.push.return_value = [{"error": "denied: [/v2/repo] access"}]
    with docker_engine(mock_client):
        res = runner.invoke(docker_app, ["push", "registry/app:1"])

    assert (res.exit_code, isinstance(res.exception, SystemExit)) == (1, True)
    assert "denied: [/v2/repo] access" in res.output


def test_docker_push_status_and_build_output_print_as_written(
    tmp_path: Path, docker_engine: Any
) -> None:
    """Push status comes from the registry and build lines from the build: their brackets print
    as written, so no word vanishes and no style or link is added. Control characters are still
    stripped (#955)."""
    status = "[link=https://example.com]Pushed[/link] [internal]"
    build_lines = ["Step [/x] done", "[internal] load build definition from Dockerfile"]
    mock_client = MagicMock()
    mock_client.images.build.return_value = (
        MagicMock(short_id="sha256:1234"),
        [{"stream": f"{line}\x07\n"} for line in build_lines],
    )
    mock_client.images.push.return_value = [{"status": status}]
    with docker_engine(mock_client):
        res_build = runner.invoke(docker_app, ["build", str(tmp_path)])
        res_push = runner.invoke(docker_app, ["push", "registry/app:1"])

    assert (res_build.exit_code, res_push.exit_code) == (0, 0)
    assert [line in res_build.output for line in build_lines] == [True, True]
    assert (status in res_push.output, "\x07" in res_build.output) == (True, False)
