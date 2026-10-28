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


def test_loki_runs_the_grafana_community_chart_whose_loki_fixes_cve_2026_21729() -> None:
    """`grafana/loki` in grafana.github.io/helm-charts became the Grafana Enterprise Logs chart,
    and its newest version still runs Loki 3.6. CVE-2026-21729 affects Loki before 3.7.0: one
    `detected_fields` request with a very large limit makes Loki allocate memory until it stops.
    The open-source chart moved to grafana-community/helm-charts, and its 20.0.2 runs Loki 3.7.9
    (#1632). The Argo CD Application installs that chart from a repository that its project
    admits. The chart takes the Loki image from its appVersion, so the Application gives the
    chart the values file and no other value, and the values set no Loki image: `loki.image` and
    `singleBinary.image` can set an older tag or digest. The values keep no
    `monitoring.selfMonitoring`, which that chart removed in 9.0.0."""
    apps = REPO_ROOT / "k8s/argocd/apps"
    application = yaml.safe_load((apps / "loki.yaml").read_text(encoding="utf-8"))
    projects = {
        doc["metadata"]["name"]: doc["spec"]
        for doc in yaml.safe_load_all((apps / "projects.yaml").read_text(encoding="utf-8"))
        if doc
    }
    values = yaml.safe_load(
        (REPO_ROOT / "k8s/logging/loki-values.yaml").read_text(encoding="utf-8")
    )
    chart_source = next(source for source in application["spec"]["sources"] if "chart" in source)

    assert {
        "chart": (chart_source["repoURL"], chart_source["chart"], chart_source["targetRevision"]),
        "project admits the repository": chart_source["repoURL"]
        in projects[application["spec"]["project"]]["sourceRepos"],
        "helm": chart_source.get("helm"),
        "loki.image": values.get("loki", {}).get("image"),
        "singleBinary.image": values.get("singleBinary", {}).get("image"),
        "monitoring.selfMonitoring": values.get("monitoring", {}).get("selfMonitoring"),
    } == {
        "chart": ("https://grafana-community.github.io/helm-charts", "loki", "20.0.2"),
        "project admits the repository": True,
        "helm": {"valueFiles": ["$values/k8s/logging/loki-values.yaml"]},
        "loki.image": None,
        "singleBinary.image": None,
        "monitoring.selfMonitoring": None,
    }
