"""The config map of the LLM gateway and the hash in its name (#2164)."""

from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.gate.k8s_render import kustomize

GATEWAY_DIR = Path("k8s/llm/gateway")


# The LiteLLM config; the gateway kustomization generates ConfigMap llm-gateway-config from it.
GATEWAY_CONFIG = GATEWAY_DIR / "config.yaml"


LLM_DIR = Path("k8s/llm")


def _rendered_gateway(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the gateway Deployment and the ConfigMap its config volume names, as
    `kubectl apply -k <directory>` applies them; the ConfigMap is empty when none has that name."""
    documents = [doc for doc in yaml.safe_load_all(kustomize(directory).stdout) if doc]
    deployment = next(
        doc
        for doc in documents
        if doc["kind"] == "Deployment" and doc["metadata"]["name"] == "llm-gateway"
    )
    volumes = {v["name"]: v for v in deployment["spec"]["template"]["spec"]["volumes"]}
    configmaps = {doc["metadata"]["name"]: doc for doc in documents if doc["kind"] == "ConfigMap"}
    return deployment, configmaps.get(volumes["config-volume"]["configMap"]["name"], {})


@pytest.mark.parametrize("directory", [LLM_DIR, GATEWAY_DIR], ids=["argo-cd", "deploy-stack"])
def check_the_gateway_mounts_a_config_map_named_by_a_hash_of_its_config(directory: Path) -> None:
    """Argo CD's `llm` Application renders `k8s/llm` with Kustomize, and deploy-stack applies
    `k8s/llm/gateway` with `kubectl apply -k`. Both give the gateway ConfigMap
    `llm-gateway-config-<hash>`, which holds `config.yaml` as git has it, and write that name into
    the Deployment's config volume. Before #1929 the name had no hash, so a changed config left
    the pod template as it was, and the gateway served the old config until a person restarted it.
    """
    _, configmap = _rendered_gateway(directory)
    name = configmap.get("metadata", {}).get("name", "")

    assert (
        re.fullmatch(r"llm-gateway-config-[a-z0-9]{10}", name) is not None,
        configmap.get("data"),
    ) == (True, {"config.yaml": GATEWAY_CONFIG.read_text(encoding="utf-8")})


def check_a_changed_gateway_config_changes_only_the_config_map_name_in_the_pod_template(
    tmp_path: Path,
) -> None:
    """A change to `config.yaml` alone changes the gateway's pod template, so Kubernetes rolls the
    Deployment onto the new config and no `kubectl rollout restart` is necessary (#1929). The
    template changes in the name of its config volume's ConfigMap and in nothing else."""
    before, after = tmp_path / "before", tmp_path / "after"
    shutil.copytree(GATEWAY_DIR, before)
    shutil.copytree(GATEWAY_DIR, after)
    config = after / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("cooldown_time: 30", "cooldown_time: 60"),
        encoding="utf-8",
    )
    (old, old_configmap), (new, new_configmap) = _rendered_gateway(before), _rendered_gateway(after)

    def unnamed(deployment: dict[str, Any]) -> dict[str, Any]:
        template = copy.deepcopy(deployment["spec"]["template"])
        for volume in template["spec"]["volumes"]:
            volume.get("configMap", {}).pop("name", None)
        return template

    assert (
        old["spec"]["template"] == new["spec"]["template"],
        unnamed(old) == unnamed(new),
        old_configmap["metadata"]["name"] == new_configmap["metadata"]["name"],
        yaml.safe_load(new_configmap["data"]["config.yaml"])["router_settings"]["cooldown_time"],
    ) == (False, True, False, 60)
