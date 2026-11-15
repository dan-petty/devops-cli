"""The gateway config keeps its errors quiet and its comments true (#5302)."""

from __future__ import annotations

import yaml

from tests.support.paths import REPO_ROOT

GATEWAY = REPO_ROOT / "k8s/llm/gateway"


def _config() -> dict:
    return yaml.safe_load((GATEWAY / "config.yaml").read_text(encoding="utf-8"))


def _deployment() -> dict:
    documents = [
        document
        for document in yaml.safe_load_all(
            (GATEWAY / "deployment.yaml").read_text(encoding="utf-8")
        )
        if document
    ]
    (deployment,) = (doc for doc in documents if doc.get("kind") == "Deployment")
    return deployment


def test_the_router_wiring_stays_out_of_the_client_error() -> None:
    assert _config()["litellm_settings"]["expose_router_debug_in_errors"] is False


def test_the_gateway_reads_no_telemetry_switch() -> None:
    """LiteLLM 1.103.11 reads neither key, so both stay gone (#5302)."""
    (container,) = _deployment()["spec"]["template"]["spec"]["containers"]
    names = {entry["name"] for entry in container["env"]}

    assert "telemetry" not in _config()["litellm_settings"]
    assert "LITELLM_TELEMETRY" not in names


def test_trusted_proxy_ranges_stays_unset() -> None:
    """The start-up warning is expected while the NodePort path exists (#5302)."""
    assert "trusted_proxy_ranges" not in _config()["general_settings"]
