"""A fake `kubectl` for the Jobs of namespace devops (#2667, #2913): the CronJobs that Jobs come
from, the Jobs a lookup lists, the Job a command creates, and the pod that runs it.

`run-job` and `devops roadmap implement --item` both make a Job through `start_job`, so both test
files use this fake. It answers by the `kubectl` verb and records every call, with the context
option taken out.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from tests.support.paths import REPO_ROOT

CRONJOB = yaml.safe_load(
    (REPO_ROOT / "k8s" / "devops" / "cronjob.yaml").read_text(encoding="utf-8")
)


def runner_cronjob_manifest() -> dict[str, Any]:
    """CronJob devops-cli-runner as the manifest names it: the template of CronJob devops-cli
    with the name, the container and the image of the runner."""
    cronjob = copy.deepcopy(CRONJOB)
    cronjob["metadata"]["name"] = "devops-cli-runner"
    container = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
    container["name"] = "runner"
    container["image"] = "ghcr.io/dan-petty/devops-cli/runner"
    container["env"] = [{"name": "DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER", "value": "true"}]
    return cronjob


@dataclass
class FakeJobs:
    """kubectl in namespace devops: the CronJob, the created Job's pod phase and exit code."""

    cronjob: dict[str, Any] | None = field(default_factory=lambda: copy.deepcopy(CRONJOB))
    runner_cronjob: dict[str, Any] | None = field(default_factory=runner_cronjob_manifest)
    phases: list[str] = field(default_factory=lambda: ["Pending", "Running"])
    exit_code: str = "0"
    listed: list[dict[str, Any]] = field(default_factory=list)
    calls: list[list[str]] = field(default_factory=list)
    created: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, cmd: list[str], **kwargs: Any) -> Any:
        import subprocess

        argv = [a for a in cmd if a not in ("--context", "test-ctx")]
        self.calls.append(argv)
        return subprocess.CompletedProcess(cmd, 0, self._answer(argv, kwargs.get("input")), "")

    def _answer(self, argv: list[str], stdin: str | None) -> str:
        verb = argv[3:5]
        if verb == ["get", "cronjob"]:
            held = self.runner_cronjob if argv[5] == "devops-cli-runner" else self.cronjob
            return json.dumps(held) if held else ""
        if verb == ["get", "jobs"]:
            return json.dumps({"items": self.listed})
        if argv[3:4] == ["create"]:
            self.created.append(json.loads(stdin or "{}"))
            return "job.batch/created\n"
        if verb == ["get", "pods"] and "phase" in argv[-1]:
            return self.phases.pop(0) if len(self.phases) > 1 else self.phases[0]
        if verb == ["get", "pods"]:
            return self.exit_code
        return ""


@pytest.fixture
def cluster_jobs(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeJobs]:
    """`kubectl` in namespace devops as a fake, for a command that makes a Job (`run-job`, and
    `roadmap implement --item` outside a runner)."""
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    fake = FakeJobs()
    with (
        patch("devops_cli.core.process.subprocess.run", side_effect=fake),
        patch("devops_cli.commands.k8s.cluster_jobs.time.sleep"),
    ):
        yield fake
