"""Tests verifying Valkey is configured as the key-value store across all Kubernetes stacks."""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"


def _extract_images_from_yaml(data: Any) -> list[str]:
    """Recursively extract all image field values from parsed YAML structures."""
    extracted: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "image":
                if isinstance(v, str):
                    extracted.append(v)
                elif isinstance(v, dict) and "repository" in v:
                    repo = v.get("repository", "")
                    tag = v.get("tag", "")
                    extracted.append(f"{repo}:{tag}" if tag else str(repo))
            else:
                extracted.extend(_extract_images_from_yaml(v))
    elif isinstance(data, list):
        for item in data:
            extracted.extend(_extract_images_from_yaml(item))
    return extracted


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
    assert len(docs) >= 2, f"Expected at least 2 YAML documents in {valkey_path}"

    deployment = next(
        (d for d in docs if isinstance(d, dict) and d.get("kind") == "Deployment"), None
    )
    assert deployment is not None, f"Expected Deployment document in {valkey_path}"

    containers = (
        deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    )
    assert containers, f"Expected container definitions in Deployment in {valkey_path}"
    container = containers[0]
    assert container.get("name") == "valkey"
    assert container.get("image") == "valkey/valkey:8.0-alpine"
    assert "valkey-server" in container.get("command", [])

    service = next((d for d in docs if isinstance(d, dict) and d.get("kind") == "Service"), None)
    assert service is not None, f"Expected Service document in {valkey_path}"
    assert service.get("metadata", {}).get("name") == "valkey"
    ports = service.get("spec", {}).get("ports", [])
    assert ports and ports[0].get("port") == 6379


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
    """Ensure no un-overridden legacy or proprietary Redis images exist in parsed k8s manifests."""
    for yml_file in K8S_DIR.rglob("*.yaml"):
        docs = list(yaml.safe_load_all(yml_file.read_text(encoding="utf-8")))
        for doc in docs:
            images = _extract_images_from_yaml(doc)
            for img in images:
                image_name = img.split("/")[-1].split(":")[0].split("@")[0].lower()
                assert image_name != "redis", (
                    f"Found proprietary redis image {img!r} in {yml_file.relative_to(REPO_ROOT)}"
                )
