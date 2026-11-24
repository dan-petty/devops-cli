"""The workloads of the devops stack on the digest that Image Updater sets (#2164)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from devops_cli.config.constants import (
    CONST_RUNNER_PHASE_AGENT,
    CONST_RUNNER_PHASE_PREPARE,
    CONST_RUNNER_PHASE_PUBLISH,
)
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


def check_both_workloads_run_the_digest_image_updater_sets_and_pull_it_only_when_missing(
    tmp_path: Path,
) -> None:
    """Application devops renders the CronJob and roadmap-service on Image Updater's digest (#1485).

    Git names the image untagged, and Argo CD adds the Application's `spec.source.kustomize.images`
    entry, which sets the digest, to the kustomization it builds, as this overlay does. A tag of
    `latest` would default the pull policy to Always, so both containers set IfNotPresent.
    """
    service = "ghcr.io/dan-petty/devops-cli/service"
    runner = "ghcr.io/dan-petty/devops-cli/runner"
    digest = f"sha256:{'0' * 64}"
    overlay = K8S_DIR / "overlays" / "homelab" / "devops"
    (tmp_path / "kustomization.yaml").write_text(
        yaml.safe_dump(
            {
                "resources": [os.path.relpath(overlay, tmp_path)],
                # Image Updater writes the entry of the runner in the Application (#2667).
                "images": [
                    {"name": service, "newTag": "latest", "digest": digest},
                    {"name": runner, "newTag": "latest", "digest": digest},
                ],
            }
        ),
        encoding="utf-8",
    )
    rendered = subprocess.run(
        ["kubectl", "kustomize", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout
    workloads = [
        d for d in yaml.safe_load_all(rendered) if d and d["kind"] in ("CronJob", "Deployment")
    ]
    pods = [
        (
            workload["kind"],
            (
                workload["spec"]["jobTemplate"]["spec"]
                if workload["kind"] == "CronJob"
                else workload["spec"]
            )["template"]["spec"],
        )
        for workload in workloads
    ]
    containers = {
        (kind, container["name"], container["image"], container["imagePullPolicy"])
        for kind, pod in pods
        for container in [*pod.get("initContainers", []), *pod["containers"]]
    }
    # Deployment `crawl4ai` pins a third-party image by tag and digest (#3884), and Renovate
    # updates the pin (#6060).
    crawl4ai = next(c for c in containers if c[1] == "crawl4ai")
    assert crawl4ai[0] == "Deployment"
    containers.discard(crawl4ai)
    # Deployment `searxng` pins a third-party image by tag and digest (#3924). A bump updates like
    # any other image (owner, 2026-11-16, #6063). Its init container `render-settings` runs the
    # same image to write the settings file (#4201), so the two name one pin.
    searxng = {c for c in containers if c[1] in ("searxng", "render-settings")}
    containers -= searxng
    assert ({c[0] for c in searxng}, len({c[2] for c in searxng})) == ({"Deployment"}, 1)
    # Each container of the runner image gets the digest, the init containers of the runner
    # template too (#3700).
    runners = {c for c in containers if c[2].startswith(runner)}
    containers -= runners
    assert (
        {c[2:] for c in runners},
        {CONST_RUNNER_PHASE_PREPARE, CONST_RUNNER_PHASE_AGENT, CONST_RUNNER_PHASE_PUBLISH}
        <= {c[1] for c in runners},
    ) == ({(f"{runner}:latest@{digest}", "IfNotPresent")}, True)
    assert containers == {
        ("CronJob", "devops-cli", f"{service}:latest@{digest}", "IfNotPresent"),
        ("Deployment", "mcp-server", "ghcr.io/dan-petty/devops-cli/mcp-server", "IfNotPresent"),
        ("Deployment", "service", f"{service}:latest@{digest}", "IfNotPresent"),
    }
