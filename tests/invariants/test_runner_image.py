"""Runner image invariants: what the committed `ci.yml` must hold
for the image of the implement Job (#2667).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

from typing import Any

import yaml

from tests.support.paths import REPO_ROOT

RUNNER_STEPS = (
    "Build and Load Runner and MCP Server Images",
    "Run Runner Image Smoke Test",
    "Scan Runner Image for Vulnerabilities",
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
    request skips the job (#4637). One job builds both targets with one bake call (#4649)."""
    job = _workflow("ci.yml")["jobs"]["mcp-server-image"]
    build = _step(job, "Build and Load Runner and MCP Server Images")
    bake = _step(job, "Write Docker Bake Definition")["run"]
    steps = [step for step in job["steps"] if step.get("name") in RUNNER_STEPS]

    assert (
        job["if"],
        job["permissions"],
        build["with"]["source"],
        build["with"]["files"],
        build["with"]["push"] in (False, "false"),
        build["with"]["load"] in (True, "true"),
        [step["if"] for step in steps],
        job.get("needs"),
    ) == (
        "(github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request')"
        " && !(startsWith(github.head_ref, 'release-please--')"
        " && github.event.pull_request.head.repo.full_name == github.repository)",
        {"contents": "read", "security-events": "write"},
        ".",
        "docker-bake.hcl",
        True,
        True,
        ["steps.image_changes.outputs.changed == 'true'"] * 3,
        None,
    )

    assert build["with"]["targets"].split() == ["runner", "mcp-server", "uv-seed"]
    assert 'target "runner"' in bake
    assert 'cache-from = ["type=registry,ref=ghcr.io/${REPOSITORY}/runner:buildcache"]' in bake
    assert 'target "uv-seed"' in bake
    assert 'cache-from = ["type=registry,ref=ghcr.io/${REPOSITORY}/uv-seed:buildcache"]' in bake

    names = [step.get("name") for step in job["steps"]]
    for name in (
        "Run Runner Image Smoke Test",
        "Scan Runner Image for Vulnerabilities",
        "Run UV Seed Image Smoke Test",
        "Scan UV Seed Image for Vulnerabilities",
        "Run MCP Server Image Smoke Test",
        "Scan MCP Server Image for Vulnerabilities",
    ):
        assert name in names
        assert _step(job, name)["if"] == "steps.image_changes.outputs.changed == 'true'"
