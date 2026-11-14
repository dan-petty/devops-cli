"""Unit tests for `devops k8s bootstrap-roadmap-key`."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from tests.support.cluster_secret_fakes import FakeCluster
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake

runner = CliRunner()


@pytest.fixture
def fake_cluster(process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch) -> FakeCluster:
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("K8S_CONTEXT", "test-ctx")
    cluster = FakeCluster()
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "sk-master-key-0001"})
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=cluster))
    return cluster


def test_bootstrap_roadmap_key_dry_run(
    fake_cluster: FakeCluster,
    keyring_store: FakeKeyring,
) -> None:
    result = runner.invoke(app, ["bootstrap-roadmap-key", "--dry-run"])

    assert result.exit_code == 0
    assert "bootstrap_roadmap_key" in result.output or "roadmap-service" in result.output


def test_bootstrap_roadmap_key_mints_and_pushes(
    fake_cluster: FakeCluster,
    keyring_store: FakeKeyring,
    web: WebFake,
    dns: DnsFake,
) -> None:
    dns.add("ai.example.com", "127.0.0.1")
    web.answer(
        "https://ai.example.com/key/generate",
        200,
        method="POST",
        body=json.dumps({"key": "sk-litellm-roadmap-service-0001"}).encode(),
    )

    result = runner.invoke(
        app,
        [
            "bootstrap-roadmap-key",
            "--gateway-url",
            "https://ai.example.com",
            "--budget",
            "25.0",
            "--rpm",
            "30",
        ],
    )

    assert result.exit_code == 0
    assert keyring_store.values.get("roadmap_service_llm_key") == "sk-litellm-roadmap-service-0001"

    # Verify request payload sent to the gateway
    requests = [r for r in web.recorded if r.url == "https://ai.example.com/key/generate"]
    assert len(requests) == 1
    assert requests[0].headers.get("authorization") == "Bearer sk-master-key-0001"
    req_json = requests[0].json
    assert req_json["key_alias"] == "roadmap-service"
    assert req_json["max_budget"] == 25.0
    assert req_json["rpm_limit"] == 30
    assert req_json["models"] == ["devops-*"]

    # Verify secret applied to the cluster
    applied = fake_cluster.applied_items()
    roadmap_secrets = [
        item
        for item in applied
        if item.get("metadata", {}).get("name") == "roadmap-service-llm-key"
    ]
    assert len(roadmap_secrets) == 1


def test_bootstrap_roadmap_key_existing_key_without_force(
    fake_cluster: FakeCluster,
    keyring_store: FakeKeyring,
    web: WebFake,
    dns: DnsFake,
) -> None:
    keyring_store.values["roadmap_service_llm_key"] = "sk-already-existing-key"

    result = runner.invoke(
        app,
        ["bootstrap-roadmap-key", "--gateway-url", "https://ai.example.com"],
    )

    assert result.exit_code == 0
    # No HTTP call was made to mint a new key
    assert not any(r.url == "https://ai.example.com/key/generate" for r in web.recorded)
    # The existing key was preserved
    assert keyring_store.values["roadmap_service_llm_key"] == "sk-already-existing-key"


def test_bootstrap_roadmap_key_force_regenerates(
    fake_cluster: FakeCluster,
    keyring_store: FakeKeyring,
    web: WebFake,
    dns: DnsFake,
) -> None:
    keyring_store.values["roadmap_service_llm_key"] = "sk-old-key"
    dns.add("ai.example.com", "127.0.0.1")
    web.answer(
        "https://ai.example.com/key/generate",
        200,
        method="POST",
        body=json.dumps({"key": "sk-new-forced-key"}).encode(),
    )

    result = runner.invoke(
        app,
        [
            "bootstrap-roadmap-key",
            "--force",
            "--gateway-url",
            "https://ai.example.com",
        ],
    )

    assert result.exit_code == 0
    assert keyring_store.values["roadmap_service_llm_key"] == "sk-new-forced-key"
    assert any(r.url == "https://ai.example.com/key/generate" for r in web.recorded)


def test_bootstrap_roadmap_key_missing_master_key_fails(
    process_fake: ProcessFake,
    keyring_store: FakeKeyring,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("K8S_CONTEXT", "test-ctx")
    empty_cluster = FakeCluster()
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=empty_cluster))

    result = runner.invoke(app, ["bootstrap-roadmap-key"])

    assert result.exit_code != 0
