"""The init container `render-settings` of SearXNG, run as the kubelet starts it (#6805).

The check renders `k8s/devops/searxng/` and runs the command of `render-settings` with `sh`. Each
mount path of the container is a directory under `tmp_path`: a ConfigMap volume holds one file for
each key of its ConfigMap, and an `emptyDir` starts empty. The variables come from the Secrets of
the scenario. A Secret that the scenario leaves out does not exist, so the kubelet starts the
container only when each reference to it is `optional: true`, and then leaves the variable out.

The `searxng` container reads its settings at `/etc/searxng/settings.yml`, the path of the image,
so the check reads the rendered file through the mount of that container. SearXNG serves
`/metrics` only when `general.open_metrics` holds a password: with an empty value it answers
HTTP 404 (`stats_open_metrics` in `searx/webapp.py`).
"""

from __future__ import annotations

import functools
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

SEARXNG_DIR = REPO_ROOT / "k8s" / "devops" / "searxng"
METRICS_SECRET = "searxng-metrics-auth"
METRICS_SECRET_REF = f"devops/{METRICS_SECRET}"
# The path at which the image reads its settings.
SETTINGS_PATH = "/etc/searxng/settings.yml"
# The special characters of a `sed` replacement, which the script escapes.
PASSWORD = r"pa&ss\wo|rd"
# The script runs `sh` and `sed` on local files; the bound stops a hung process, not a slow one.
RENDER_TIMEOUT_SECONDS = 10

Secrets = Mapping[str, Mapping[str, str]]


@functools.cache
def _rendered() -> tuple[dict[str, Any], ...]:
    documents = yaml.load_all(kustomize(SEARXNG_DIR).stdout, Loader=yaml.CSafeLoader)
    return tuple(document for document in documents if isinstance(document, dict))


def _object(kind: str, name: str) -> dict[str, Any]:
    (found,) = (
        document
        for document in _rendered()
        if document["kind"] == kind and document["metadata"]["name"] == name
    )
    return found


def _pod() -> dict[str, Any]:
    pod: dict[str, Any] = _object("Deployment", "searxng")["spec"]["template"]["spec"]
    return pod


def _container(pod: dict[str, Any], name: str) -> dict[str, Any]:
    containers: list[dict[str, Any]] = [*pod.get("initContainers", []), *pod["containers"]]
    (found,) = (container for container in containers if container["name"] == name)
    return found


def _volume_dirs(pod: dict[str, Any], container: dict[str, Any], root: Path) -> dict[str, Path]:
    """A directory under `root` for each volume that `container` mounts, filled as the kubelet
    fills the volume."""
    volumes = {volume["name"]: volume for volume in pod["volumes"]}
    dirs: dict[str, Path] = {}
    for mount in container.get("volumeMounts", []):
        volume = volumes[mount["name"]]
        directory = root / mount["name"]
        directory.mkdir(exist_ok=True)
        if "configMap" in volume:
            assert "items" not in volume["configMap"], "the check models a ConfigMap volume whole"
            data = _object("ConfigMap", volume["configMap"]["name"]).get("data", {})
            for key, text in data.items():
                (directory / key).write_text(text, encoding="utf-8")
        else:
            assert "emptyDir" in volume, f"the check models no volume like {mount['name']}"
        dirs[mount["name"]] = directory
    return dirs


def _environment(container: dict[str, Any], secrets: Secrets) -> dict[str, str]:
    """The variables of `container` as the kubelet sets them, from the Secrets of the scenario."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    for entry in container.get("env", []):
        if "value" in entry:
            env[entry["name"]] = entry["value"]
            continue
        ref = entry["valueFrom"]["secretKeyRef"]
        value = secrets.get(ref["name"], {}).get(ref["key"])
        if value is not None:
            env[entry["name"]] = value
            continue
        assert ref.get("optional") is True, (
            f"the kubelet does not start {container['name']}: CreateContainerConfigError, "
            f"Secret {ref['name']} or its key {ref['key']} is missing and the reference is "
            "required"
        )
    return env


def _run_render(tmp_path: Path, secrets: Secrets) -> tuple[subprocess.CompletedProcess[str], Any]:
    """Run `render-settings` with `secrets`; give its process and the `general.open_metrics`
    that the `searxng` container reads."""
    pod = _pod()
    init = _container(pod, "render-settings")
    dirs = _volume_dirs(pod, init, tmp_path)
    mounts = sorted(
        ((mount["mountPath"], dirs[mount["name"]]) for mount in init["volumeMounts"]),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    argv = []
    for part in [*init["command"], *init.get("args", [])]:
        for mount_path, directory in mounts:
            part = part.replace(mount_path, str(directory))
        argv.append(part)
    process = subprocess.run(
        argv,
        env=_environment(init, secrets),
        capture_output=True,
        text=True,
        check=False,
        timeout=RENDER_TIMEOUT_SECONDS,
    )
    (settings_mount,) = (
        mount
        for mount in _container(pod, "searxng")["volumeMounts"]
        if mount["mountPath"] == SETTINGS_PATH
    )
    assert settings_mount["name"] in dirs, "the searxng container reads a file of no init volume"
    settings = dirs[settings_mount["name"]] / settings_mount.get("subPath", "")
    rendered = yaml.safe_load(settings.read_text(encoding="utf-8")) if settings.is_file() else None
    open_metrics = (rendered or {}).get("general", {}).get("open_metrics", "<no file>")
    return process, open_metrics


def _log_lines(process: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in (process.stdout + process.stderr).splitlines() if line.strip()]


def check_render_settings_without_the_metrics_secret_turns_the_endpoint_off(
    tmp_path: Path,
) -> None:
    """With no metrics Secret, the pod starts and SearXNG serves no `/metrics` (#6805)."""
    process, open_metrics = _run_render(tmp_path, {})
    lines = _log_lines(process)

    assert (
        process.returncode,
        open_metrics,
        len(lines),
        all(METRICS_SECRET_REF in line for line in lines),
    ) == (0, "", 1, True), (process.stdout, process.stderr)


def check_render_settings_with_the_metrics_secret_writes_its_password(tmp_path: Path) -> None:
    """With the metrics Secret, the settings hold its password, `sed` specials as they are."""
    secrets = {METRICS_SECRET: {"username": "searxng", "password": PASSWORD}}

    process, open_metrics = _run_render(tmp_path, secrets)

    assert (process.returncode, open_metrics, _log_lines(process)) == (0, PASSWORD, []), (
        process.stderr
    )
