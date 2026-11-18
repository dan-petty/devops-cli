"""The checks of the self-hosted Renovate CronJob and ConfigMap (#6020)."""

from __future__ import annotations

from typing import Any

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
OVERLAY = K8S_DIR / "overlays" / "homelab" / "devops"


def _documents() -> list[dict[str, Any]]:
    return applied_documents(OVERLAY)


def check_the_renovate_config_removes_the_token_file() -> None:
    """ConfigMap renovate-config must remove the token file and quote the key."""
    try:
        from devops_cli.k8s.renovate_token import token_file_problems
    except ImportError:

        def token_file_problems(config_js: str) -> list[str]:
            problems: list[str] = []
            token_path = "/token/github-token"
            if token_path not in config_js:
                problems.append(f"the script does not name the default token path {token_path}")
            if "readFileSync" not in config_js:
                problems.append(f"the script does not read {token_path}")
            if "unlinkSync" not in config_js:
                problems.append(f"the script does not remove {token_path}")
            if "readFileSync" in config_js and "unlinkSync" in config_js:
                if config_js.find("unlinkSync") < config_js.find("readFileSync"):
                    problems.append(f"the script removes {token_path} before the read")
            return problems

    docs = _documents()
    (configmap,) = [
        d
        for d in docs
        if d.get("kind") == "ConfigMap" and d.get("metadata", {}).get("name") == "renovate-config"
    ]
    config_js = configmap["data"]["config.js"]
    problems = token_file_problems(config_js)
    assert not problems, f"config.js has problems with /token/github-token: {problems}"
    assert "'token':" in config_js, "config.js must export the quoted key 'token'"


def check_the_renovate_container_mounts_the_token_volume_writable() -> None:
    """Container renovate of CronJob renovate must mount the token volume writable."""
    docs = _documents()
    (cronjob,) = [
        d
        for d in docs
        if d.get("kind") == "CronJob" and d.get("metadata", {}).get("name") == "renovate"
    ]
    pod = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    (container,) = [c for c in pod["containers"] if c["name"] == "renovate"]
    (token_mount,) = [m for m in container.get("volumeMounts", []) if m["name"] == "token"]
    assert not token_mount.get("readOnly", False), (
        "volumeMount 'token' of container renovate must not be readOnly"
    )
