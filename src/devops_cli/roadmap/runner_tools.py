"""The tools that the runner image must hold, and the check of each one (#3072).

The runner Job runs the checks of the gate and the hooks of the repository. A tool that the image
lacks gives a different result there than in the devcontainer or in CI: a check fails for a missing
program, or a test that needs the program skips. `RUNNER_TOOLS` lists every program the image must
hold, where the image gets it, and the command that proves it runs. `NOT_IN_RUNNER` names each
program that the image does not hold, with the reason, so a person sees that a decision was made.

The image build runs `python -m devops_cli.roadmap.runner_tools` as its last step, so an image
that lacks a tool, or holds it at another version than its pin, does not build. A test in
`tests/roadmap/test_roadmap_runner_tools.py` fails when a program that a `devops ci` row, a hook of
`.pre-commit-config.yaml`, a live-marked test, a required job of `ci.yml` or an entry of the tools
lock needs is in neither table.

Where the version comes from: a dev dependency has the version of the lockfile (the installed
distribution), a tool of the lock has the version of `tools.lock`, and a tool that the Dockerfile
pins by image digest or release has the version in its `pin`. A test compares each pin with the
Dockerfile. A package of the distribution (apt) and a program of the base image have no pin.
"""

from __future__ import annotations

import importlib.metadata
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_PYTHON_VERSION
from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES
from devops_cli.output import print_error, print_success
from devops_cli.tools_lock import load_tools_lock

# The directory in which the image links the commands of the tools lock, and its user data root.
TOOLS_DIR = Path("/opt/devops-tools")
TOOLS_BIN_DIR = TOOLS_DIR / "bin"
USER_DATA_ROOT_VARIABLE = "DEVOPS_CLI_USER_DATA_ROOT"

# The pins that only the Dockerfile holds. A test reads the Dockerfile and compares.
UV_VERSION = "0.13.6"
GH_VERSION = "2.102.1"
ACTIONLINT_VERSION = "1.17.0"
NODE_MAJOR = "24"


class ToolSource(StrEnum):
    """Where the image gets a tool."""

    BASE = "base"
    APT = "apt"
    DEV_GROUP = "dev-group"
    TOOLS_LOCK = "tools-lock"
    IMAGE_PIN = "image-pin"
    PROJECT = "project"


@dataclass(frozen=True)
class RunnerTool:
    """One program of the image. `check` is the command that proves it runs; with no `check` the
    program only has to be on PATH. `package` is the distribution of a dev dependency when its name
    differs from the program. `pin` is the text that the output of `check` must hold, for a tool
    that the Dockerfile pins. `needed_by` says why the image holds it: `ci:<row>`, `hook:<id>`,
    `gate:<job>`, `test:<marker>` or `job`."""

    name: str
    source: ToolSource
    needed_by: tuple[str, ...]
    check: tuple[str, ...] = ()
    package: str = ""
    pin: str = ""


def _dev(name: str, *needed_by: str, package: str = "") -> RunnerTool:
    return RunnerTool(
        name, ToolSource.DEV_GROUP, needed_by, (name, "--version"), package=package or name
    )


def _locked(name: str, *needed_by: str) -> RunnerTool:
    return RunnerTool(name, ToolSource.TOOLS_LOCK, needed_by, (name, "--version"))


def _apt(name: str, *needed_by: str, check: tuple[str, ...] = ()) -> RunnerTool:
    return RunnerTool(name, ToolSource.APT, needed_by, check or (name, "--version"))


def _base(name: str, *needed_by: str) -> RunnerTool:
    return RunnerTool(name, ToolSource.BASE, needed_by)


RUNNER_TOOLS: tuple[RunnerTool, ...] = (
    RunnerTool(
        "uv",
        ToolSource.IMAGE_PIN,
        ("ci:lockfile", "ci:build", "ci:uv-check", "hook:ast-grep-scan"),
        ("uv", "--version"),
        pin=UV_VERSION,
    ),
    RunnerTool(
        "python",
        ToolSource.IMAGE_PIN,
        ("ci:git", "ci:test-settings"),
        ("python", "--version"),
        pin=f"Python {DEFAULT_PYTHON_VERSION}.",
    ),
    RunnerTool("python3", ToolSource.BASE, ("test:live",), ("python3", "--version")),
    RunnerTool(
        "devops",
        ToolSource.PROJECT,
        ("ci:docs", "ci:openspec", "ci:zizmor", "hook:openspec-gate"),
        ("devops", "--version"),
    ),
    _apt("git", "ci:git", "job"),
    RunnerTool("gh", ToolSource.IMAGE_PIN, ("job",), ("gh", "--version"), pin=GH_VERSION),
    RunnerTool(
        "node",
        ToolSource.IMAGE_PIN,
        ("ci:openspec",),
        ("node", "--version"),
        pin=f"v{NODE_MAJOR}.",
    ),
    _locked("openspec", "ci:openspec", "hook:openspec-gate"),
    _dev("pytest", "ci:test", package="pytest"),
    _dev("ruff", "ci:lint", "ci:format", "hook:ruff-check", "hook:ruff-format"),
    _dev("mypy", "ci:typecheck"),
    _dev("bandit", "ci:security"),
    _dev("deptry", "ci:deps"),
    _dev("ast-grep", "ci:constructs", "hook:ast-grep-scan", package="ast-grep-cli"),
    _dev("zizmor", "ci:zizmor"),
    _dev("pre-commit", "job"),
    RunnerTool(
        "actionlint",
        ToolSource.IMAGE_PIN,
        ("ci:actionlint",),
        ("actionlint", "-version"),
        pin=ACTIONLINT_VERSION,
    ),
    _apt("shellcheck", "ci:actionlint"),
    _apt("curl", "test:live"),
    _apt("jq", "test:live"),
    _locked("trivy", "gate:static"),
    _locked("promtool", "gate:test"),
    _base("nice", "ci:security"),
    _base("sh", "test:live"),
    _base("bash", "test:live"),
    _base("find", "test:live"),
    _base("sleep", "test:live"),
    _base("echo", "test:live"),
    _base("pwd", "test:live"),
    _base("true", "test:live"),
    _base("false", "test:live"),
)

# Why the image does not hold a program that a source of the gate or an entry of the tools lock
# names. The key is the program. A test fails when a program is in neither table.
_NO_CLUSTER = (
    "No check, hook, test or job of the gate runs it. The Job has no cluster token and no "
    "container engine."
)
_SCANNER = (
    "A scanner of `devops scan report`. The Static Analysis job of `ci.yml` installs none of "
    "them, so the gate reports it as not run. A scanner on PATH also fails tests that pass in the "
    "gate (#2165). The runner does the same as the gate."
)
_NO_GATE_STEP = "No step of a required job of `ci.yml` runs it."
NOT_IN_RUNNER: dict[str, str] = {
    "kubectl": _NO_CLUSTER,
    "kustomize": _NO_CLUSTER,
    "helm": _NO_CLUSTER,
    "argo": _NO_CLUSTER,
    "argocd": _NO_CLUSTER,
    "cloudflared": _NO_CLUSTER,
    "kubectl-argo-rollouts": _NO_CLUSTER,
    "k9s": _NO_CLUSTER,
    "minikube": _NO_CLUSTER,
    "docker": _NO_CLUSTER,
    "kube-linter": _SCANNER,
    "popeye": _SCANNER,
    "pluto": _SCANNER,
    "kubeconform": _SCANNER,
    "tflint": _SCANNER,
    "gitleaks": _SCANNER,
    "osv-scanner": _SCANNER,
    "golangci-lint": _SCANNER,
    "semgrep": (
        "Only the rule-pack job of `ci.yml` installs it, and only when a rule file changes."
    ),
    "gh-dash": _NO_GATE_STEP,
    "tuicr": _NO_GATE_STEP,
    "devcontainers-cli": _NO_GATE_STEP,
    "npm": (
        "The audit row runs `npm audit`. The image deletes npm, because the scan of the image "
        "reports the packages that npm bundles, and a Job installs no tool."
    ),
    "zsh": (
        "The image of the GitHub runner has no zsh, so the tests that need it skip in the gate too."
    ),
    "bwrap": "The tests marked `bwrap` run only with `-m bwrap`, and the gate does not select it.",
}


def tool_names() -> tuple[str, ...]:
    """The program of each tool of the table, in order."""
    return tuple(tool.name for tool in RUNNER_TOOLS)


def expected_text(tool: RunnerTool) -> str:
    """The text that the output of the check of `tool` must hold, or the empty string when the tool
    has no pin: a package of the distribution and a program of the base image."""
    match tool.source:
        case ToolSource.DEV_GROUP:
            return importlib.metadata.version(tool.package)
        case ToolSource.TOOLS_LOCK:
            return load_tools_lock().tools()[tool.name].version
        case ToolSource.PROJECT:
            return importlib.metadata.version("devops-cli")
        case ToolSource.IMAGE_PIN:
            return tool.pin
        case _:
            return ""


def _pin_failure(tool: RunnerTool) -> str | None:
    """Why a tool of the lock is not linked at its locked version in the tools directory, or None.
    This is `devops install-tools --check` for that one tool."""
    done = run_subprocess(
        [
            "devops",
            "install-tools",
            "--check",
            "--tool",
            tool.name,
            "--target-dir",
            str(TOOLS_BIN_DIR),
        ],
        extra_allowed_env=[USER_DATA_ROOT_VARIABLE],
    )
    if done.returncode == 0:
        return None
    return MESSAGES.roadmap.runner_tool_off_pin.format(
        tool=tool.name, output=(done.stdout + done.stderr).strip()
    )


def tool_failure(tool: RunnerTool) -> str | None:
    """Why `tool` fails its check, or None when it runs and holds its pin."""
    texts = MESSAGES.roadmap
    if tool.source is ToolSource.TOOLS_LOCK and (failure := _pin_failure(tool)):
        return failure
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
        return texts.runner_tool_version.format(tool=tool.name, wanted=wanted, output=output)
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
