"""The tools that the runner image must hold, and the check of each one (#3072).

The runner Job runs the checks of the gate and the hooks of the repository. A tool that the image
lacks gives a different result there than in the devcontainer or in CI: a check fails for a missing
program, or a test that needs the program skips. `RUNNER_TOOLS` lists every program the image must
hold, where the image gets it, and the command that proves it runs. `NOT_IN_RUNNER` names each
program that a step of the Job does not count on, with the reason: the image does not hold it, or
no source of the gate runs it in a Job. So a person sees that a decision was made.

The smoke test of the runner image in `ci.yml` and `release.yml` runs
`python -m devops_cli.roadmap.runner_tools` on the built image, so an image that lacks a tool, or
holds a tool whose version command fails, fails the check. A test in
`tests/roadmap/test_roadmap_runner_tools.py` fails when a program that a `devops ci` row, a hook of
`.pre-commit-config.yaml`, a live-marked test or a required job of `ci.yml` needs is in neither
table.

The module holds no tool version (#5585). The runner image builds FROM the devtools image, which
names the source of each tool, and the `Dockerfile` pins that image by digest (#4361). `uv.lock`
gives the version of each dev dependency. A copy here would be a second pin for each update to
change. Only a dev dependency and the project must print a
version: the version of their installed distribution, so the program on PATH is the one of the venv.
"""

from __future__ import annotations

import importlib.metadata
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES
from devops_cli.output import print_error, print_success


class ToolSource(StrEnum):
    """Where the image gets a tool."""

    BASE = "base"
    DEVTOOLS = "devtools"
    DEV_GROUP = "dev-group"
    PROJECT = "project"


@dataclass(frozen=True)
class RunnerTool:
    """One program of the image. `check` is the command that proves it runs; with no `check` the
    program only has to be on PATH. `package` is the distribution of a dev dependency when its name
    differs from the program. `needed_by` says why the image holds it: `ci:<row>`, `hook:<id>`,
    `gate:<job>`, `test:<marker>` or `job`."""

    name: str
    source: ToolSource
    needed_by: tuple[str, ...]
    check: tuple[str, ...] = ()
    package: str = ""


def _dev(name: str, *needed_by: str, package: str = "") -> RunnerTool:
    return RunnerTool(
        name, ToolSource.DEV_GROUP, needed_by, (name, "--version"), package=package or name
    )


def _devtools(name: str, *needed_by: str, check: tuple[str, ...] = ()) -> RunnerTool:
    return RunnerTool(name, ToolSource.DEVTOOLS, needed_by, check or (name, "--version"))


def _base(name: str, *needed_by: str) -> RunnerTool:
    return RunnerTool(name, ToolSource.BASE, needed_by)


RUNNER_TOOLS: tuple[RunnerTool, ...] = (
    _devtools("uv", "ci:lockfile", "ci:build", "ci:uv-check", "hook:ast-grep-scan"),
    _devtools(
        "python",
        "ci:git",
        "ci:test-settings",
        "ci:k8s",
        "ci:startup-imports",
        "ci:swallowed-failures",
        "ci:test-tree",
        "ci:domain",
    ),
    _devtools("python3", "test:live"),
    RunnerTool(
        "devops",
        ToolSource.PROJECT,
        ("ci:docs", "ci:openspec", "ci:zizmor", "hook:openspec-gate"),
        ("devops", "--version"),
    ),
    _devtools("git", "ci:git", "ci:lint", "ci:constructs", "ci:domain", "job"),
    _devtools("gh", "job"),
    _devtools("node", "ci:openspec"),
    _devtools("openspec", "ci:openspec", "hook:openspec-gate"),
    _devtools("tofu", "gate:static"),
    _dev("pytest", "ci:test", "ci:bwrap", package="pytest"),
    _dev("ruff", "ci:lint", "ci:format", "hook:ruff-check", "hook:ruff-format"),
    _dev("mypy", "ci:typecheck"),
    _dev("bandit", "ci:security"),
    _dev("deptry", "ci:deps"),
    _dev("ast-grep", "ci:constructs", "hook:ast-grep-scan", package="ast-grep-cli"),
    _dev("zizmor", "ci:zizmor"),
    _dev("pre-commit", "job"),
    _devtools("curl", "test:live"),
    _devtools("jq", "test:live"),
    _devtools("promtool", "gate:test"),
    _devtools("actionlint", "ci:actionlint", "gate:static", "hook:devops-ci-workflows-pre-push"),
    _devtools("shellcheck", "ci:actionlint"),
    _devtools("trivy", "gate:static"),
    _devtools("kubectl", "test:live", check=("kubectl", "version", "--client")),
    _devtools("kube-linter", "gate:static", check=("kube-linter", "version")),
    _devtools("osv-scanner", "ci:audit", "gate:static"),
    _devtools("npm", "ci:audit"),
    _devtools("zsh", "test:live"),
    _devtools("ps", "test:live"),
    _base("nice", "ci:security"),
    _base(
        "env",
        "hook:ast-grep-scan",
        "hook:ast-grep-test",
        "hook:openspec-gate",
        "hook:devops-ci-pre-push",
        "hook:devops-ci-workflows-pre-push",
    ),
    _base(
        "timeout",
        "hook:branch-current",
        "hook:devops-ci-pre-push",
        "hook:devops-ci-workflows-pre-push",
    ),
    _base("sh", "test:live"),
    _base("bash", "test:live"),
    _base("find", "test:live"),
    _base("sleep", "test:live"),
    _base("echo", "test:live"),
    _base("pwd", "test:live"),
    _base("true", "test:live"),
    _base("false", "test:live"),
)

# Why a step of the Job does not count on a program. The key is the program. The devtools image
# holds most of these programs, but no source of the gate runs them in a Job. A test fails when a
# program that a source of the gate names is in neither table.
_NO_CLUSTER = (
    "No check, hook, test or job of the gate runs it. The Job has no cluster token, and its pod "
    "cannot run a container engine: it has no capability and a read-only root."
)
_SCANNER = (
    "A scanner of `devops scan report`. The Static Analysis job of `ci.yml` installs none of "
    "them, so the gate reports it as not run, and no step of a Job counts on it."
)
_NO_GATE_STEP = "No step of a required job of `ci.yml` runs it."
# A hook of `.pre-commit-config.yaml` that runs a program that the image does not hold, with the
# programs it runs. The Job leaves the hook out of the configuration it gives `pre-commit` when one
# of its programs is not on PATH, because no agent can repair a missing program. The checks of the
# pull request run the hook (#3134). The image holds actionlint (#3108), so no hook needs this
# table today; a test holds that each program here is in `NOT_IN_RUNNER`.
HOOK_PROGRAMS: dict[str, tuple[str, ...]] = {}


def hooks_without_programs(search_path: str | None = None) -> tuple[str, ...]:
    """The ids of the hooks of `HOOK_PROGRAMS` that a program is missing for, found on
    `search_path` (the PATH of the process when None)."""
    return tuple(
        hook
        for hook, programs in HOOK_PROGRAMS.items()
        if any(shutil.which(program, path=search_path) is None for program in programs)
    )


NOT_IN_RUNNER: dict[str, str] = {
    "vale": "Only the live docs test runs it; no step of a required job of `ci.yml` runs it.",
    "kustomize": _NO_CLUSTER,
    "helm": _NO_CLUSTER,
    "argo": _NO_CLUSTER,
    "argocd": _NO_CLUSTER,
    "cloudflared": _NO_CLUSTER,
    "kubectl-argo-rollouts": _NO_CLUSTER,
    "k9s": _NO_CLUSTER,
    "minikube": _NO_CLUSTER,
    "docker": "The image holds no Docker engine and no `docker` program. " + _NO_CLUSTER,
    "popeye": _SCANNER,
    "pluto": _SCANNER,
    "kubeconform": _SCANNER,
    "tflint": _SCANNER,
    "gitleaks": _SCANNER,
    "golangci-lint": _SCANNER,
    "semgrep": (
        "Only the workflow `rule-pack.yml` installs it, and only when a rule file changes."
    ),
    "ansible-core": (
        "No gate row, hook or job starts Ansible. Only `devops infra` starts it, on a workstation."
    ),
    "gh-dash": _NO_GATE_STEP,
    "tuicr": _NO_GATE_STEP,
    "devcontainers-cli": _NO_GATE_STEP,
    "style-dictionary": (
        "Only the Design Tokens job runs it, to build the tokens of `design/`. A Job runs no "
        "design token build, so the pull request checks it."
    ),
    "bwrap": (
        "Only the `bwrap` row runs the tests marked `bwrap`, and it skips with the cause on a host "
        "that cannot make the sandbox."
    ),
}


def tool_names() -> tuple[str, ...]:
    """The program of each tool of the table, in order."""
    return tuple(tool.name for tool in RUNNER_TOOLS)


def expected_text(tool: RunnerTool) -> str:
    """The version of the installed distribution that the output of the check of `tool` must hold:
    for a dev dependency and for the project. The empty string for every other tool, because the
    devtools image gives its version."""
    match tool.source:
        case ToolSource.DEV_GROUP:
            return importlib.metadata.version(tool.package)
        case ToolSource.PROJECT:
            return importlib.metadata.version("devops-cli")
        case _:
            return ""


def tool_failure(tool: RunnerTool) -> str | None:
    """Why `tool` fails its check, or None when it is on PATH, its version command exits 0, and a
    dev dependency or the project prints its installed version."""
    texts = MESSAGES.roadmap
    if not tool.check:
        if shutil.which(tool.name) is None:
            return texts.runner_tool_missing.format(tool=tool.name)
        return None
    done = run_subprocess(list(tool.check))
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0:
        return texts.runner_tool_failed.format(
            tool=tool.name, command=" ".join(tool.check), status=done.returncode
        )
    wanted = expected_text(tool)
    if wanted and wanted not in output:
        return texts.runner_tool_other_version.format(tool=tool.name, wanted=wanted, output=output)
    return None


def failures(tools: Sequence[RunnerTool] = RUNNER_TOOLS) -> list[str]:
    """The failure of each tool that fails its check, in the order of the table."""
    return [text for tool in tools if (text := tool_failure(tool)) is not None]


def main() -> int:
    """Check every tool of the table. Print each failure. Exit status 1 when any tool fails."""
    problems = failures()
    for problem in problems:
        print_error(problem, prefix=False)
    if problems:
        return 1
    print_success(MESSAGES.roadmap.runner_tools_ready.format(count=len(RUNNER_TOOLS)), prefix=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
