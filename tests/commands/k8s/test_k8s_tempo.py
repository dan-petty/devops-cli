"""Unit tests for Tempo Helm values, stack integration, and k8s command integration."""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_k8s_port_forward_tempo_dry_run(runner: CliRunner) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        from devops_cli.commands.k8s import app as k8s_app

        result = runner.invoke(
            k8s_app,
            ["port-forward", "--stack", "infra"],
        )
        assert (
            result.exit_code,
            "tempo" in result.output,
            "3200" in result.output,
            "pyroscope" in result.output,
            "4040" in result.output,
        ) == (0, True, True, True, True)
    finally:
        set_dry_run(False)


def test_k8s_configure_urls_tempo_dry_run(runner: CliRunner) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        from devops_cli.commands.k8s import app as k8s_app

        result = runner.invoke(
            k8s_app,
            ["configure-urls", "--stack", "infra"],
        )
        assert (
            result.exit_code,
            "tempo.url" in result.output,
            "pyroscope.url" in result.output,
        ) == (0, True, True)
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_shows_tempo_connection_info(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake, keyring_store: Any
) -> None:
    """deploy-stack for infra prints where Tempo and Pyroscope listen."""
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "version"),
        ProcessAnswer(returncode=0, stdout="v3.17.0\n"),
    )

    result = cli(["k8s", "deploy-stack", "--stack", "infra", "--no-push-secrets"])

    assert (
        result.exit_code,
        "Tempo HTTP API: http://localhost:3200 (namespace: otel)" in result.output,
        "Tempo OTLP Traces: localhost:4317 (gRPC) / localhost:4318 (HTTP)" in result.output,
        "Pyroscope UI: http://localhost:4040 (namespace: monitoring)" in result.output,
    ) == (0, True, True, True)
