"""The real `docker buildx imagetools inspect`'s answers, recorded, which `ImagetoolsFake` replays
(#1994).

`record_runs` resolves each image of `RECORDED_IMAGES` with the command that
`devops_cli.k8s.image_pins.inspect_command` builds, as an anonymous client (an empty Docker
configuration directory), and keeps each run's exit code, standard output and standard error.
The images cover what a run can meet: a Docker Hub manifest list and an OCI index that resolve, a
missing tag on Docker Hub and on Quay, a Docker Hub repository that does not exist, and a GHCR
repository that refuses an anonymous token.

Record again when the command changes, on a host with network and docker buildx:

    uv run python -c "from tests.support.imagetools_recording import record_runs; record_runs()"

`tests/k8s/test_imagetools_contract.py` fails until the record holds the command the code builds.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from devops_cli.k8s.image_pins import inspect_command

RECORDED_IMAGES = (
    "cloudflare/cloudflared:2026.10.4",
    "ghcr.io/berriai/litellm:v1.103.0",
    "ollama/ollama:0.0.0-does-not-exist",
    "quay.io/argoproj/argocd:v0.0.0-missing",
    "dan-petty/no-such-repository-1994:1.0",
    "ghcr.io/dan-petty/no-such-image-1994:1.0",
)
_RECORD = files("tests").joinpath("fixtures", "imagetools_runs", "recorded_runs.json")


@dataclass(frozen=True)
class RecordedRun:
    """One resolve: the image, the command after the program name, and what the tool answered."""

    image: str
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def load_recorded_runs() -> tuple[str, dict[str, RecordedRun]]:
    """The buildx version that recorded the runs, and each run by its image."""
    record: dict[str, Any] = json.loads(_RECORD.read_text(encoding="utf-8"))
    runs = {
        run["image"]: RecordedRun(
            image=run["image"],
            argv=tuple(run["argv"]),
            returncode=int(run["returncode"]),
            stdout=run["stdout"],
            stderr=run["stderr"],
        )
        for run in record["runs"]
    }
    return str(record["buildx"]), runs


def record_runs(destination: Path | None = None) -> None:
    """Resolve each recorded image with the real tool and write the record."""
    version = subprocess.run(
        ["docker", "buildx", "version"], capture_output=True, text=True, check=True
    ).stdout.split()[1]
    runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as config:
        for image in RECORDED_IMAGES:
            command = inspect_command(image)
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                env={"DOCKER_CONFIG": config, "PATH": "/usr/local/bin:/usr/bin:/bin"},
            )
            runs.append(
                {
                    "image": image,
                    "argv": command[1:],
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                }
            )
    target = destination or Path(str(_RECORD))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"buildx": version, "runs": runs}, indent=2) + "\n", encoding="utf-8"
    )
