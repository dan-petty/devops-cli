"""The infra checkout that row 13 of `devops repos onboard` reads before it writes the cluster."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# pytest can load this file before HOME is isolated, so it imports no support module when it loads.
if TYPE_CHECKING:
    from tests.support.github_repository import OnboardHarness

_APPLICATION = """apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: agents
  namespace: argocd
"""


@pytest.fixture(autouse=True)
def infra_checkout(
    onboard_github: OnboardHarness, config: Callable[..., Path], tmp_path: Path
) -> Path:
    """The Kubernetes folder of the one infra repo of `infra.repos`: a checkout whose profile names
    it, with an Application and a Secret table. The git fake of the harness gives it a clean
    `HEAD` at `origin/main`."""
    repo = tmp_path / "infra"
    (repo / ".git").mkdir(parents=True)
    (repo / ".devops").mkdir()
    (repo / ".devops" / "project.toml").write_text('[kubernetes]\ndir = "k8s"\n', "utf-8")
    (repo / "k8s" / "argocd" / "apps").mkdir(parents=True)
    (repo / "k8s" / "argocd" / "apps" / "agents.yaml").write_text(_APPLICATION, "utf-8")
    (repo / "k8s" / "cluster-secrets.toml").write_text("secret = []\n", "utf-8")
    config(infra={"repos": [{"repo": "example-org/infra", "path": str(repo)}]})
    return repo / "k8s"
