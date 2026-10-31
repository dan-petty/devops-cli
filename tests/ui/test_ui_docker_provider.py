"""Tests for the dashboard Docker data provider using the DockerEngine fake."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ui.data_providers import DockerSummary, fetch_docker_status


def test_fetch_docker_status_success(docker_engine: Any) -> None:
    """fetch_docker_status returns container records when Docker daemon is available."""
    mock_container = MagicMock()
    mock_container.id = "c1a2b3c4d5e6f7a8"
    mock_container.name = "valkey-cache"
    mock_container.image.tags = ["valkey/valkey:8.0-alpine"]
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.list.return_value = [mock_container]

    with docker_engine(mock_client):
        summary = fetch_docker_status()

    assert isinstance(summary, DockerSummary)
    assert (
        summary.connected,
        len(summary.containers),
        summary.containers[0]["name"],
        summary.containers[0]["status"],
    ) == (True, 1, "valkey-cache", "running")


def test_fetch_docker_status_failure() -> None:
    """fetch_docker_status gracefully returns disconnected summary on daemon error."""
    from devops_cli.docker.engine import DockerEngineService

    def failing_factory(**_kwargs: Any) -> Any:
        raise Exception("Daemon down")

    DockerEngineService.install(failing_factory)
    try:
        summary = fetch_docker_status()
        assert isinstance(summary, DockerSummary)
        assert (summary.connected, summary.containers) == (
            False,
            [],
        )
    finally:
        DockerEngineService.reset_instance()


def test_fetch_docker_status_refused_endpoint(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """fetch_docker_status reports connected=False with refusal message on SSRF violation."""
    monkeypatch.setenv("DOCKER_HOST", "tcp://192.0.2.1:2375")
    with patch("docker.DockerClient") as mock_docker_client:
        summary = fetch_docker_status()

    assert isinstance(summary, DockerSummary)
    assert (
        summary.connected,
        summary.containers,
        mock_docker_client.called,
        "DOCKER_HOST" in (summary.error_message or ""),
    ) == (False, [], False, True)
