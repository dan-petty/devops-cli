"""Runner image invariants: what the committed `Dockerfile`, `release.yml` and `ci.yml` must hold
for the image of the implement Job (#2667).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

import re
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


def test_the_runner_stage_adds_the_dev_dependencies_and_git_to_the_builder() -> None:
    """Verify that the runner stage builds on `builder` and syncs the lockfile with the dev group.

    The builder holds uv, gh, the Node runtime and the pinned OpenSpec, and `uv sync --locked`
    with no `--no-dev` adds pytest, ruff and mypy to its venv.
    """
    runner = _stages()["runner"]
    runs = _runs(runner)
    sync = [run for run in runs if "uv sync" in run]
    apt = [run for run in runs if "apt-get install" in run]

    assert (
        runner[0][1:],
        len(sync),
        "--locked" in sync[0],
        "--no-dev" in sync[0],
        len(apt),
        "git" in apt[0].split(),
    ) == (["builder", "AS", "runner"], 1, True, False, 1, True)


def test_the_runner_stage_removes_what_only_the_build_needs() -> None:
    """Verify that the runner stage deletes npm, pip and the uv cache of root.

    The builder installs OpenSpec with npm and fills the cache of root while it syncs. A Job runs
    none of them, and the scan of the image reports the findings in them (npm bundles `undici`
    and `brace-expansion`, pip vendors `certifi`, `urllib3` and `msgpack`), so the stage deletes
    them, as the service stage deletes pip.
    """
    runs = " ".join(_runs(_stages()["runner"]))

    assert [
        path
        for path in (
            "/usr/local/lib/node_modules/npm",
            "/usr/local/bin/npm",
            "/root/.cache/uv",
            "/usr/local/lib/python3.14/site-packages/pip*",
        )
        if "rm -rf" not in runs or path not in runs
    ] == []


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


def test_uv_run_finds_an_interpreter_in_the_runner_image() -> None:
    """Verify that `uv run` in a worktree can find a Python in the runner image.

    The image forbids a Python download (`UV_PYTHON_DOWNLOADS=never`), and `.python-version` of a
    checkout can name a patch release that the digest-pinned base image does not have. So the
    stage names the base image's interpreter in `UV_PYTHON`, which uv then uses for any version
    of that minor release.
    """
    env = env_of(_stages()["runner"])
    wanted = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()

    assert (env.get("UV_PYTHON"), wanted.count(".")) == ("/usr/local/bin/python3", 2)


def test_the_runner_stage_comes_before_service_so_that_the_default_build_is_the_service() -> None:
    """Verify that `service` is still the last stage, which a build with no `--target` makes."""
    names = list(_stages())

    assert (names.index("runner") < names.index("service"), names[-1]) == (True, "service")


def _release_job() -> dict[str, Any]:
    job: dict[str, Any] = _workflow("release.yml")["jobs"]["runner-image"]
    return job


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_the_release_publishes_the_runner_image_next_to_the_service_image() -> None:
    """Verify that the release builds, smoke-tests, scans, pushes by digest, attests and tags the
    runner image, in that order, and only in the run that creates a release."""
    job = _release_job()
    names = [step.get("name", "") for step in job["steps"]]
    indices = [names.index(name) for name in RUNNER_STEPS]
    meta = next(step for step in job["steps"] if step.get("id") == "meta")
    push = _step(job, "Build and Push Runner Image")["with"]
    attest = _step(job, "Attest Build Provenance")["with"]

    assert (
        job["if"],
        job["needs"],
        job["env"]["RUNNER_IMAGE"],
        indices == sorted(indices),
        _step(job, "Build and Load Runner Image")["with"]["target"],
        push["target"],
        "push-by-digest=true" in push["outputs"],
        push["no-cache-filters"],
        attest["subject-name"],
        [line.strip() for line in meta["with"]["tags"].splitlines() if line.strip()],
    ) == (
        "needs.release-please.outputs.release_created == 'true'",
        "release-please",
        "ghcr.io/${{ github.repository }}/runner",
        True,
        "runner",
        "runner",
        True,
        "runner",
        "ghcr.io/${{ github.repository }}/runner",
        ["type=raw,value=${{ needs.release-please.outputs.tag_name }}", "type=raw,value=latest"],
    )


def test_the_release_scans_the_runner_image_for_high_and_critical_findings() -> None:
    """Verify the scan: vulnerabilities only, HIGH and CRITICAL, unfixed ones ignored, exit 1."""
    trivy = _step(_release_job(), "Scan Runner Image for Vulnerabilities")["with"]

    assert (
        trivy["scanners"],
        trivy["severity"],
        trivy["ignore-unfixed"],
        str(trivy["exit-code"]),
    ) == ("vuln", "HIGH,CRITICAL", True, "1")


def test_the_pull_request_check_builds_the_runner_image_and_pushes_nothing() -> None:
    """Verify that CI builds the runner target for a pull request, loads it, pushes nothing, and
    builds only when image content changed (the rule of the Service image job)."""
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
        "github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request'",
        {"contents": "read"},
        "runner",
        True,
        True,
        ["steps.image_changes.outputs.changed == 'true'"] * 3,
        None,
    )


def test_the_smoke_test_runs_uv_in_a_copy_of_the_checkout() -> None:
    """Verify that the smoke test runs `uv run --locked ruff --version` in a copy of the checkout,
    on a read-only root as the Job does: the step and the job run `uv run` in a worktree."""
    run = _step(_workflow("ci.yml")["jobs"]["runner-image"], RUNNER_STEPS[1])["run"]
    lines = [line for line in run.splitlines() if "uv run --locked ruff --version" in line]

    assert (len(lines), "--read-only" in lines[0], ".git" in lines[0]) == (1, True, True)


def test_the_smoke_test_of_the_runner_image_is_the_same_in_ci_and_in_the_release() -> None:
    """Verify that both workflows run one smoke test, in a read-only container with no capability,
    which checks the tools of a step through the table `RUNNER_TOOLS` and not through a list of
    its own, bounds the size of the image, and checks that the image holds no compiler (#3072)."""
    ci = _step(_workflow("ci.yml")["jobs"]["runner-image"], RUNNER_STEPS[1])["run"].strip()
    release = _step(_release_job(), RUNNER_STEPS[1])["run"].strip()

    assert (
        ci == release,
        "--read-only" in ci,
        "--cap-drop ALL" in ci,
        "no-new-privileges" in ci,
        "-m devops_cli.roadmap.runner_tools" in ci,
        "-gt 3000000000" in ci,
        [
            line
            for line in ci.splitlines()
            if "--entrypoint" in line and line.endswith('"$IMAGE" --version')
        ],
    ) == (True, True, True, True, True, True, [])


def test_the_documented_size_bound_of_the_runner_image_is_the_bound_of_the_smoke_test() -> None:
    """Verify that `k8s/README.md` states the byte bound that the smoke test enforces (#3072)."""
    run = _step(_workflow("ci.yml")["jobs"]["runner-image"], RUNNER_STEPS[1])["run"]
    (bound,) = re.findall(r'"\$size" -gt (\d+)', run)
    readme = (REPO_ROOT / "k8s" / "README.md").read_text(encoding="utf-8")

    assert f"more than {bound} bytes" in readme
