"""Tests verifying Valkey is configured as the key-value store across all Kubernetes stacks."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"


def test_argocd_values_specifies_valkey_image() -> None:
    """Verify ArgoCD Helm values.yaml configures Valkey instead of proprietary Redis."""
    values_path = K8S_DIR / "argocd" / "values.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "redis" in data, "ArgoCD values.yaml must contain redis configuration block"
    redis_cfg = data["redis"]
    assert redis_cfg.get("enabled") is True, "Redis component must be enabled"
    assert "image" in redis_cfg, "Redis component must explicitly override container image"
    assert redis_cfg["image"]["repository"] == "valkey/valkey"
    assert redis_cfg["image"]["tag"] == "8.0-alpine"


def test_llm_valkey_manifest_specification() -> None:
    """Verify LLM stack valkey.yaml defines Valkey deployment and service."""
    valkey_path = K8S_DIR / "llm" / "valkey.yaml"
    assert valkey_path.is_file(), f"Missing {valkey_path}"

    docs = list(yaml.safe_load_all(valkey_path.read_text(encoding="utf-8")))
    assert len(docs) >= 2, "Expected Deployment and Service in valkey.yaml"

    deployment = next(d for d in docs if d.get("kind") == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container["name"] == "valkey"
    assert container["image"] == "valkey/valkey:8.0-alpine"
    assert "valkey-server" in container["command"]

    service = next(d for d in docs if d.get("kind") == "Service")
    assert service["metadata"]["name"] == "valkey"
    assert service["spec"]["ports"][0]["port"] == 6379


def test_open_webui_values_connects_to_valkey() -> None:
    """Verify Open-WebUI Helm values connects websocket manager to Valkey service."""
    webui_values_path = K8S_DIR / "llm" / "values-open-webui.yaml"
    assert webui_values_path.is_file(), f"Missing {webui_values_path}"

    with open(webui_values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "websocket" in data, "values-open-webui.yaml must configure websocket"
    ws = data["websocket"]
    assert ws.get("enabled") is True
    assert "valkey.llm.svc.cluster.local:6379" in ws.get("url", "")
    assert ws.get("redis", {}).get("enabled") is False, "Embedded Redis subchart must be disabled"


def test_no_proprietary_redis_images_in_stack() -> None:
    """Ensure no un-overridden legacy or proprietary Redis images exist in k8s manifests."""
    forbidden_image_patterns = [
        "docker.io/library/redis",
        "redis:7.",
        "redis:6.",
        "redis:latest",
        "redis:alpine",
    ]

    for yml_file in K8S_DIR.rglob("*.yaml"):
        content = yml_file.read_text(encoding="utf-8")
        for pattern in forbidden_image_patterns:
            assert pattern not in content, (
                f"Found forbidden redis pattern {pattern!r} in {yml_file.relative_to(REPO_ROOT)}"
            )
