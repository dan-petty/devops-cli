"""The Tempo configuration that chart `tempo` renders parses with the Tempo image of the chart (#6730).

The limits of #6616 put two keys in the search block of the query frontend that Tempo 3.1.1 does
not have, and pod `otel/tempo-0` stopped at start with `failed parsing config`. Only the Tempo
binary of the pinned version knows its keys. So the check renders the chart of the Argo CD
Application `tempo` as Argo CD does, and starts the image of the rendered `tempo` container on the
rendered ConfigMaps, with the arguments of the container and `-config.verify=true`. Tempo then
parses the file strictly, checks it and exits: 1 on an unknown key or a warning, 0 when the
configuration is valid. It starts no module, so it needs no storage, and the container gets no
network. A chart update that moves Tempo to a new version runs the new binary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Final

from tests.gate.k8s_render import ARGOCD_APPLICATIONS, chart_objects

TEMPO_APPLICATION: Final = ARGOCD_APPLICATIONS / "tempo.yaml"

TEMPO_CONTAINER: Final[str] = "tempo"

# The flag of Tempo that parses and checks the configuration, then exits. The flag takes a value:
# `-config.verify` alone exits 2 with "flag needs an argument".
VERIFY_FLAG: Final[str] = "-config.verify=true"

# The first run pulls the image, which took about 5 s; the bound stops a hung pull.
VERIFY_TIMEOUT_SECONDS: Final[int] = 90

# Tempo runs as user 10001, which owns no folder of the host, so every user can read the mounts.
READABLE_FOLDER: Final[int] = 0o755
READABLE_FILE: Final[int] = 0o644


def _rendered(kind: str) -> list[dict[str, Any]]:
    """The rendered objects of the Tempo chart of this kind."""
    return [document for document in chart_objects(TEMPO_APPLICATION) if document["kind"] == kind]


def _config_mounts(pod: dict[str, Any], container: dict[str, Any], folder: Path) -> list[str]:
    """Write each ConfigMap that `container` mounts to a folder under `folder`, and return the
    `--volume` options that mount each folder read-only at its mount path."""
    data = {
        document["metadata"]["name"]: document.get("data", {})
        for document in _rendered("ConfigMap")
    }
    config_maps = {
        volume["name"]: volume["configMap"]["name"]
        for volume in pod.get("volumes", [])
        if "configMap" in volume
    }
    options: list[str] = []
    for mount in container.get("volumeMounts", []):
        if mount["name"] not in config_maps:
            continue
        mounted = folder / mount["name"]
        mounted.mkdir()
        mounted.chmod(READABLE_FOLDER)
        for key, text in data[config_maps[mount["name"]]].items():
            (mounted / key).write_text(text, encoding="utf-8")
            (mounted / key).chmod(READABLE_FILE)
        options += ["--volume", f"{mounted}:{mount['mountPath']}:ro"]
    return options


def check_the_rendered_tempo_config_parses_with_the_tempo_image_of_the_chart(
    tmp_path: Path,
) -> None:
    """The image of the rendered `tempo` container parses and checks the rendered configuration
    with the arguments of the container, so the pod passes the parse at start (#6730)."""
    (statefulset,) = _rendered("StatefulSet")
    pod = statefulset["spec"]["template"]["spec"]
    (container,) = (entry for entry in pod["containers"] if entry["name"] == TEMPO_CONTAINER)
    arguments = [*container.get("args", []), VERIFY_FLAG]
    command = [
        "docker",
        "run",
        "--rm",
        "--quiet",
        "--network",
        "none",
        *_config_mounts(pod, container, tmp_path),
        container["image"],
        *arguments,
    ]

    verified = subprocess.run(
        command, check=False, capture_output=True, text=True, timeout=VERIFY_TIMEOUT_SECONDS
    )

    assert verified.returncode == 0, (
        f"{TEMPO_APPLICATION}: {container['image']} {' '.join(arguments)} exited "
        f"{verified.returncode} on the rendered configuration: "
        f"{(verified.stdout + verified.stderr).strip()}"
    )
