"""Runner image invariants: what the committed `ci.yml` must hold
for the image of the implement Job (#2667).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

from typing import Any

import yaml

from tests.support.paths import REPO_ROOT

RUNNER_STEPS = (
    "Build and Load Runner Image",
    "Run Runner Image Smoke Test",
    "Scan Runner Image for Vulnerabilities",
    "Build and Push Runner Image",
    "Attest Build Provenance",
    "Tag the Attested Runner Image",
)


def _workflow(name: str) -> dict[str, Any]:
    parsed = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_the_pull_request_check_builds_the_runner_image_and_pushes_nothing() -> None:
    """Verify that CI builds the runner target for a pull request, loads it, pushes nothing, and
    builds only when image content changed (the rule of the Service image job). The release pull
    request skips the job (#4637)."""
    job = _workflow("ci.yml")["jobs"]["runner-image"]
    build = _step(job, "Build and Load Runner Image")
    steps = [step for step in job["steps"] if step.get("name") in RUNNER_STEPS[:3]]

    assert (
        job["if"],
        job["permissions"],
        build["with"]["target"],
        build["with"]["push"] in (False, "false"),
        build["with"]["load"] in (True, "true"),
        [step["if"] for step in steps],
        job.get("needs"),
    ) == (
        "(github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request')"
        " && !(startsWith(github.head_ref, 'release-please--')"
        " && github.event.pull_request.head.repo.full_name == github.repository)",
        {"contents": "read", "security-events": "write"},
        "runner",
        True,
        True,
        ["steps.image_changes.outputs.changed == 'true'"] * 3,
        None,
    )
