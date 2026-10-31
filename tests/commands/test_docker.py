"""Unit tests for docker CLI commands (devops_cli.commands.docker)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app

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


def test_docker_commands(tmp_path: Path, docker_engine: Any, docker_client: Any) -> None:
    """Verify docker images, build, push, and prune subcommands."""
    mock_client = docker_client
    mock_img = MagicMock()
    mock_img.tags = ["alpine:latest"]
    mock_img.short_id = "sha256:1234"
    mock_img.attrs = {"Size": 5000000}
    mock_client.images.list.return_value = [mock_img]
    mock_client.images.build.return_value = (mock_img, [{"stream": "Step 1/1 : FROM alpine\n"}])
    mock_client.images.push.return_value = [{"status": "Pushing layer 1"}]
    mock_client.containers.prune.return_value = {"SpaceReclaimed": 10485760}
    mock_client.networks.prune.return_value = {}
    mock_client.images.prune.return_value = {}

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


def test_docker_client_fixture_is_autospecced(docker_client: Any) -> None:
    """The docker_client fixture pins DockerClient attributes and signatures."""
    with pytest.raises(AttributeError, match="Mock object has no attribute 'system'"):
        _ = docker_client.system
    with pytest.raises(TypeError, match="got an unexpected keyword argument 'volumes'"):
        docker_client.containers.prune(volumes=True)


def test_docker_stats_dry_run() -> None:
    """Verify docker stats --dry-run outputs the plan without touching Docker."""
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res = runner.invoke(docker_app, ["stats", "--name", "myapp", "--interval", "1.5"])
        assert res.exit_code == 0
        assert "DOCKER GET /containers/json?name=myapp" in res.output
        assert "DOCKER GET /containers/<container-id>/stats" in res.output
    finally:
        set_dry_run(False)


def test_docker_stats_sdk_table(docker_engine: Any, docker_client: Any) -> None:
    """Verify docker stats table is built from typed Engine API container samples."""
    from devops_cli.commands.docker import _build_docker_stats_table, _format_bytes

    mock_client = docker_client
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


def test_docker_has_no_analyze_layers_command() -> None:
    """dive is gone (#2427), and no command in its place analyzes the layers of an image."""
    result = runner.invoke(docker_app, ["analyze-layers", "alpine:latest"])

    assert (result.exit_code, "No such command" in result.output) == (2, True)


def test_docker_client_and_error_branches(
    tmp_path: Path, docker_engine: Any, docker_client: Any
) -> None:
    """Verify docker _client connection, push errors, and dry-run branches."""
    from devops_cli.commands.docker import _engine
    from devops_cli.dry_run import set_dry_run

    # 1. An unreachable daemon is surfaced as a clean CLI exit rather than a traceback.
    with patch("docker.DockerClient", side_effect=Exception("Daemon not running")):
        with pytest.raises(typer.Exit) as raised:
            _engine()
        assert raised.value.exit_code is not None

    # 3. Dry run branches for build, push, prune, images
    set_dry_run(True)
    try:
        res_b_dry = runner.invoke(
            docker_app,
            ["build", str(tmp_path), "--file", str(tmp_path / "Dockerfile"), "--no-cache"],
        )
        assert res_b_dry.exit_code == 0
        assert "DOCKER POST /build" in res_b_dry.output

        res_p_dry = runner.invoke(docker_app, ["push", "myimage:latest"])
        assert res_p_dry.exit_code == 0
        assert "DOCKER POST /images/myimage:latest/push" in res_p_dry.output

        res_pr_dry = runner.invoke(docker_app, ["prune"])
        assert res_pr_dry.exit_code == 0
        assert "DOCKER POST /containers/prune" in res_pr_dry.output

        res_img_dry = runner.invoke(docker_app, ["images"])
        assert res_img_dry.exit_code == 0
        assert "DOCKER GET /images/json" in res_img_dry.output
    finally:
        set_dry_run(False)

    # 4. Push invalid image name
    from http import HTTPStatus

    from docker.errors import APIError

    mock_bad_req = MagicMock(status_code=HTTPStatus.BAD_REQUEST)
    docker_client.images.push.side_effect = APIError(
        "invalid name", response=mock_bad_req, explanation="invalid reference format"
    )
    with docker_engine(docker_client):
        res_bad_img = runner.invoke(docker_app, ["push", "Invalid Name!"])
        assert (
            res_bad_img.exit_code,
            "Invalid Docker image name format" in res_bad_img.output,
        ) == (
            1,
            True,
        )

    # 5. Push stream error
    docker_client.images.push.side_effect = None
    docker_client.images.push.return_value = [{"error": "denied: access forbidden"}]
    with docker_engine(docker_client):
        res_push_err = runner.invoke(docker_app, ["push", "org/repo:tag"])
        assert res_push_err.exit_code == 1
        assert "access forbidden" in res_push_err.output


def test_docker_images_and_build_formatting(
    tmp_path: Path, docker_engine: Any, docker_client: Any
) -> None:
    """Verify docker images tag formatting and build stream logging."""
    mock_client = docker_client
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


def test_docker_push_registry_error_prints_as_written_and_exits_1(
    docker_engine: Any, docker_client: Any
) -> None:
    """A push error is the registry's text: `[/v2/repo]` in it is text, not a Rich closing tag
    that ends the command in a MarkupError traceback instead of a clean exit 1 (#955)."""
    mock_client = docker_client
    mock_client.images.push.return_value = [{"error": "denied: [/v2/repo] access"}]
    with docker_engine(mock_client):
        res = runner.invoke(docker_app, ["push", "registry/app:1"])

    assert res.exit_code == 1
    assert isinstance(res.exception, SystemExit)
    assert "denied: [/v2/repo] access" in res.output


def test_docker_push_status_and_build_output_print_as_written(
    tmp_path: Path, docker_engine: Any, docker_client: Any
) -> None:
    """Push status comes from the registry and build lines from the build: their brackets print
    as written, so no word vanishes and no style or link is added. Control characters are still
    stripped (#955)."""
    status = "[link=https://example.com]Pushed[/link] [internal]"
    build_lines = ["Step [/x] done", "[internal] load build definition from Dockerfile"]
    mock_client = docker_client
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


@pytest.mark.parametrize(
    "image_name",
    [
        "localhost:5000/app:1.0",
        "example.com:443/a/b:c",
        "[::1]:5000/app:1",
    ],
)
def test_docker_push_accepts_registry_ports(
    image_name: str, docker_engine: Any, docker_client: Any
) -> None:
    """Registry endpoints with ports reach client.images.push without regex rejection."""
    mock_client = docker_client
    mock_client.images.push.return_value = [{"status": "Pushed"}]
    with docker_engine(mock_client):
        res = runner.invoke(docker_app, ["push", image_name])

    assert (res.exit_code, mock_client.images.push.call_args[0][0]) == (0, image_name)


def test_docker_push_escapes_progress_text_without_markup_error(
    docker_engine: Any, docker_client: Any
) -> None:
    """An image reference with bracket markup prints literally in the progress line (#1108)."""
    mock_client = docker_client
    mock_client.images.push.return_value = [{"status": "Pushed"}]
    with docker_engine(mock_client):
        res = runner.invoke(docker_app, ["push", "app:1[/x]"])

    assert (res.exit_code, "app:1[/x]" in res.output) == (0, True)


def test_docker_push_server_error_prints_daemon_explanation(
    docker_engine: Any, docker_client: Any
) -> None:
    """A 500 APIError prints the daemon explanation as plain text and exits 1 (#1108)."""
    from http import HTTPStatus

    from docker.errors import APIError

    mock_resp = MagicMock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_client = docker_client
    mock_client.images.push.side_effect = APIError(
        "internal error", response=mock_resp, explanation="server crashed"
    )
    with docker_engine(mock_client):
        res = runner.invoke(docker_app, ["push", "registry/app:1"])

    assert (res.exit_code, "server crashed" in res.output) == (1, True)


def test_docker_push_invalid_repository_prints_error_and_exits_1(
    docker_engine: Any, docker_client: Any
) -> None:
    """InvalidRepository error from docker-py prints invalid-name error and exits 1 (#1108)."""
    from docker.errors import InvalidRepository

    mock_client = docker_client
    mock_client.images.push.side_effect = InvalidRepository("invalid repo name")
    with docker_engine(mock_client):
        res = runner.invoke(docker_app, ["push", "--", "-reg.example.com/app:1"])

    assert (
        res.exit_code,
        "Invalid Docker image name format" in res.output,
        "invalid repo name" in res.output,
    ) == (1, True, True)


def test_docker_prune_calls_order_and_filters(docker_engine: Any, docker_client: Any) -> None:
    """devops docker prune --force calls containers, networks, and images in order."""
    with docker_engine(docker_client):
        res = runner.invoke(docker_app, ["prune", "--force"])

    assert res.exit_code == 0
    assert docker_client.mock_calls == [
        call.containers.prune(),
        call.networks.prune(),
        call.images.prune(),
    ]


def test_docker_prune_with_volumes(docker_engine: Any, docker_client: Any) -> None:
    """devops docker prune --force --volumes calls containers, networks, images, and volumes."""
    with docker_engine(docker_client):
        res = runner.invoke(docker_app, ["prune", "--force", "--volumes"])

    assert res.exit_code == 0
    assert docker_client.mock_calls == [
        call.containers.prune(),
        call.networks.prune(),
        call.images.prune(),
        call.volumes.prune(),
    ]


def test_docker_prune_confirmation_abort_sends_no_requests(
    docker_engine: Any, docker_client: Any
) -> None:
    """Without --force, aborting the confirmation prompt sends no prune request."""
    with docker_engine(docker_client):
        with patch("typer.confirm", side_effect=typer.Abort):
            res = runner.invoke(docker_app, ["prune"])

    assert res.exit_code != 0
    assert docker_client.mock_calls == []


def test_docker_prune_confirmation_accepted_runs_prune(
    docker_engine: Any, docker_client: Any
) -> None:
    """Without --force, accepting the confirmation runs the prune sequence."""
    with docker_engine(docker_client):
        with patch("typer.confirm", return_value=True):
            res = runner.invoke(docker_app, ["prune"])

    assert res.exit_code == 0
    assert docker_client.mock_calls == [
        call.containers.prune(),
        call.networks.prune(),
        call.images.prune(),
    ]


def test_docker_prune_dry_run_sends_no_requests(docker_engine: Any, docker_client: Any) -> None:
    """devops docker prune --dry-run sends no prune request."""
    with docker_engine(docker_client):
        res = runner.invoke(docker_app, ["prune", "--dry-run"])

    assert res.exit_code == 0
    assert "DOCKER POST /containers/prune" in res.output
    assert docker_client.mock_calls == []


def test_docker_prune_reclaimed_space(docker_engine: Any, docker_client: Any) -> None:
    """Pruning sums SpaceReclaimed across collection replies and formats as MB."""
    docker_client.containers.prune.return_value = {"SpaceReclaimed": 5242880}
    docker_client.networks.prune.return_value = {"NetworksDeleted": ["bridge1"]}
    docker_client.images.prune.return_value = {"SpaceReclaimed": 5242880}
    docker_client.volumes.prune.return_value = {"SpaceReclaimed": 1048576}

    with docker_engine(docker_client):
        res_no_vol = runner.invoke(docker_app, ["prune", "--force"])
        assert res_no_vol.exit_code == 0
        assert "10 MB" in res_no_vol.output

        res_vol = runner.invoke(docker_app, ["prune", "--force", "--volumes"])
        assert res_vol.exit_code == 0
        assert "11 MB" in res_vol.output


def test_docker_prune_reclaimed_space_null_value_counts_as_zero(
    docker_engine: Any, docker_client: Any
) -> None:
    """A missing or null SpaceReclaimed value counts as 0 bytes."""
    docker_client.containers.prune.return_value = {"SpaceReclaimed": None}
    docker_client.networks.prune.return_value = {}
    docker_client.images.prune.return_value = None

    with docker_engine(docker_client):
        res = runner.invoke(docker_app, ["prune", "--force"])

    assert res.exit_code == 0
    assert "0 MB" in res.output


def test_docker_prune_daemon_api_error_exits_1(docker_engine: Any, docker_client: Any) -> None:
    """A daemon error from any prune call exits 1 with one error line and no traceback."""
    from docker.errors import APIError

    docker_client.containers.prune.side_effect = APIError("daemon communication broken")

    with docker_engine(docker_client):
        res = runner.invoke(docker_app, ["prune", "--force"])

    assert res.exit_code == 1
    assert "daemon communication broken" in res.output
    assert "Traceback" not in res.output
