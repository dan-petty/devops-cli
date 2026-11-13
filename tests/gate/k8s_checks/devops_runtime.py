"""The workloads of the devops stack on the digest that Image Updater sets (#2164)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from devops_cli.k8s.crawl4ai_check import CRAWL4AI_IMAGE
from devops_cli.k8s.searxng_check import SEARXNG_IMAGE
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
    digest = f"sha256:{'0' * 64}"
    overlay = K8S_DIR / "overlays" / "homelab" / "devops"
    (tmp_path / "kustomization.yaml").write_text(
        yaml.safe_dump(
            {
                "resources": [os.path.relpath(overlay, tmp_path)],
                "images": [{"name": service, "newTag": "latest", "digest": digest}],
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
    containers = {
        (workload["kind"], container["name"], container["image"], container["imagePullPolicy"])
        for workload in workloads
        for container in (
            workload["spec"]["jobTemplate"]["spec"]
            if workload["kind"] == "CronJob"
            else workload["spec"]
        )["template"]["spec"]["containers"]
    }
    # The runner has no entry here: Image Updater writes its own entry (#2667).
    # Deployment `crawl4ai` pins a third-party image by tag and digest (#3884). `devops k8s
    # crawl4ai-check` names the image it was written for (#3894), so a bump fails here until a
    # person runs the command against the new image and sets the constant.
    crawl4ai = next(c for c in containers if c[1] == "crawl4ai")
    assert crawl4ai[0] == "Deployment"
    assert crawl4ai[2] == CRAWL4AI_IMAGE, (
        f"k8s/devops/crawl4ai/deployment.yaml pins {crawl4ai[2]}, but `devops k8s crawl4ai-check` "
        f"was written for {CRAWL4AI_IMAGE}. Run `uv run devops k8s crawl4ai-check` against the new "
        "image, then set CRAWL4AI_IMAGE in src/devops_cli/k8s/crawl4ai_check.py."
    )
    containers.discard(crawl4ai)
    # Deployment `searxng` pins a third-party image by tag and digest (#3924). `devops k8s
    # searxng-check` names the image it was written for (#3929), so a bump fails here until a
    # person runs the command against the new image and sets the constant.
    searxng = next(c for c in containers if c[1] == "searxng")
    assert searxng[0] == "Deployment"
    assert searxng[2] == SEARXNG_IMAGE, (
        f"k8s/devops/searxng/deployment.yaml pins {searxng[2]}, but `devops k8s searxng-check` "
        f"was written for {SEARXNG_IMAGE}. Run `uv run devops k8s searxng-check` against the new "
        "image, then set SEARXNG_IMAGE in src/devops_cli/k8s/searxng_check.py."
    )
    containers.discard(searxng)
    assert containers == {
        ("CronJob", "devops-cli", f"{service}:latest@{digest}", "IfNotPresent"),
        ("CronJob", "runner", "ghcr.io/dan-petty/devops-cli/runner", "IfNotPresent"),
        ("CronJob", "stage", f"{service}:latest@{digest}", "IfNotPresent"),
        ("Deployment", "mcp-server", "ghcr.io/dan-petty/devops-cli/mcp-server", "IfNotPresent"),
        ("Deployment", "service", f"{service}:latest@{digest}", "IfNotPresent"),
    }
