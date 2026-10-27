"""Kubernetes manifest invariants: what the committed manifests under `k8s/` must hold."""

from __future__ import annotations

import yaml

from tests.support.paths import REPO_ROOT

# The Proxy Read Timeout of the Cloudflare edge, which only an Enterprise zone can change.
CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS = 125


def test_the_gateway_keeps_a_streamed_chat_reply_open_under_the_edge_timeout() -> None:
    """A streamed reply with no data for 125 s is cut at the edge, so the gateway writes a
    keepalive comment sooner, the time before the first token included (#2365)."""
    config = yaml.safe_load((REPO_ROOT / "k8s/llm/gateway/config.yaml").read_text(encoding="utf-8"))

    interval = config["litellm_settings"].get("sse_keepalive_ping_interval_seconds")

    assert isinstance(interval, int | float)
    assert 0 < interval < CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS
