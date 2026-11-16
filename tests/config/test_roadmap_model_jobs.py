"""The value of `roadmap.model_jobs` in the ConfigMap template of the cluster (#6017)."""

from __future__ import annotations

import yaml

from devops_cli.config.settings import RoadmapConfig
from tests.support.paths import REPO_ROOT


def test_the_cluster_template_lets_six_model_jobs_run_and_the_code_default_stays_2() -> None:
    """The owner chose 6 model Jobs for all repositories together: the implement, stage and
    fix-checks Jobs, with the fix-checks Jobs first."""
    document = yaml.safe_load((REPO_ROOT / "k8s/devops/configmap.example.yaml").read_text("utf-8"))
    roadmap = yaml.safe_load(document["data"]["devops-cli.yaml"])["roadmap"]

    assert (RoadmapConfig().model_jobs, RoadmapConfig.model_validate(roadmap).model_jobs) == (2, 6)
