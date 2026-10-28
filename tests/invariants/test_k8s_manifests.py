"""Kubernetes manifest invariants: what the committed manifests under `k8s/` must hold."""

from __future__ import annotations

import yaml
from packaging.version import Version

from tests.support.paths import REPO_ROOT

# The Proxy Read Timeout of the Cloudflare edge, which only an Enterprise zone can change.
CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS = 125

# The first Ollama release that runs a multimodal embedding model, such as embeddinggemma-2,
# through llama-server, its runner on Linux. 0.40.0 ran that model on Apple MLX only (#2395).
OLLAMA_FIRST_LLAMA_SERVER_EMBEDDING_RELEASE = Version("0.40.4")


def test_the_gateway_keeps_a_streamed_chat_reply_open_under_the_edge_timeout() -> None:
    """A streamed reply with no data for 125 s is cut at the edge, so the gateway writes a
    keepalive comment sooner, the time before the first token included (#2365)."""
    config = yaml.safe_load((REPO_ROOT / "k8s/llm/gateway/config.yaml").read_text(encoding="utf-8"))

    interval = config["litellm_settings"].get("sse_keepalive_ping_interval_seconds")

    assert isinstance(interval, int | float)
    assert 0 < interval < CLOUDFLARE_PROXY_READ_TIMEOUT_SECONDS


def test_every_ollama_tier_runs_one_release_that_serves_multimodal_embedding_models() -> None:
    """Each tier keeps its models in the node's /var/lib/ollama, and a node that moves to another
    tier reads that store with the other tier's release, so every tier and its init container run
    one image: a release that runs embeddinggemma-2 on Linux (#2395)."""
    profiles = REPO_ROOT / "k8s/llm/profiles/ollama-profiles.yaml"
    tiers = [doc for doc in yaml.safe_load_all(profiles.read_text(encoding="utf-8")) if doc]
    images = {
        container["image"]
        for tier in tiers
        for container in [
            *tier["spec"]["template"]["spec"].get("initContainers", []),
            *tier["spec"]["template"]["spec"]["containers"],
        ]
    }

    assert len(images) == 1
    repository, tag = next(iter(images)).split(":")
    assert repository == "ollama/ollama"
    assert Version(tag) >= OLLAMA_FIRST_LLAMA_SERVER_EMBEDDING_RELEASE
