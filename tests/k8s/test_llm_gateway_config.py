"""The gateway config keeps its errors quiet (#5302)."""

from __future__ import annotations

import yaml

from tests.support.paths import REPO_ROOT

GATEWAY = REPO_ROOT / "k8s/llm/gateway"


def _config() -> dict:
    return yaml.safe_load((GATEWAY / "config.yaml").read_text(encoding="utf-8"))


def test_the_router_wiring_stays_out_of_the_client_error() -> None:
    assert _config()["litellm_settings"]["expose_router_debug_in_errors"] is False
