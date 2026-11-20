"""Runner image invariants: what the committed `Dockerfile`, `release.yml` and `ci.yml` must hold
for the image of the implement Job (#2667).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

from typing import Any

import yaml

from tests.support.dockerfile import env_of, stages
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


def _stages() -> dict[str, list[list[str]]]:
    return stages((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))


def _runs(stage: list[list[str]]) -> list[str]:
    return [" ".join(words[1:]) for words in stage if words[0].upper() == "RUN"]


def test_the_runner_image_holds_no_npm_pip_or_uv_cache() -> None:
    """Verify that no stage of the runner image copies npm, that `runner-deps` deletes pip, and
    that each uv install of the image keeps the uv cache of root in a cache mount.

    A Job installs no tool, and the scan of the image reports the findings in them (npm bundles
    `undici` and `brace-expansion`, pip vendors `certifi`, `urllib3` and `msgpack`), as the
    service stage deletes pip. Only the `builder` stage, which installs OpenSpec, holds npm.
    """
    all_stages = _stages()
    chain = ["runner", "runner-deps", "deps"]
    words = [word for name in chain for line in all_stages[name] for word in line]
    runner_deps_runs = " ".join(_runs(all_stages["runner-deps"]))

    assert (
        [word for word in words if "node_modules/npm" in word],
        "rm -rf" in runner_deps_runs,
        "/usr/local/lib/python3.14/site-packages/pip*" in runner_deps_runs.split(),
        [
            name
            for name in chain
            for line in all_stages[name]
            if line[0] == "RUN"
            and "uv pip" in " ".join(line)
            and "--mount=type=cache,target=/root/.cache/uv" not in line
        ],
    ) == ([], True, True, [])


def test_the_runner_stage_runs_as_user_1000_and_starts_devops() -> None:
    """Verify the user, the entrypoint and the environment of the runner stage."""
    runner = _stages()["runner"]
    env = env_of(runner)

    assert (
        [words for words in runner if words[0].upper() in {"USER", "ENTRYPOINT"}],
        env["PATH"].split(":")[:2],
        env["OPENSPEC_TELEMETRY"],
        env["OPENSPEC_NO_UPDATE_CHECK"],
        env["DO_NOT_TRACK"],
        env["DEVOPS_CLI_DATA_DIR"].startswith(env["HOME"]),
        env["UV_CACHE_DIR"].startswith(env["HOME"]),
    ) == (
        [["USER", "1000:1000"], ["ENTRYPOINT", "[devops]"]],
        ["/app/.venv/bin", "/opt/devops-tools/bin"],
        "0",
        "1",
        "1",
        True,
        True,
    )


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
