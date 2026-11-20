"""The tools that a runner Job needs, the check of each one (#3072), and the coder environment of
the checkout of a Job (#6517).

The runner Job runs the checks of the gate and the hooks of the repository. A tool that the Job
lacks gives a different result there than in the devcontainer or in CI: a check fails for a missing
program, or a test that needs the program skips. `RUNNER_TOOLS` lists every program that a Job
needs, where it comes from, and the command that proves it runs. `NOT_IN_RUNNER` names each
program that a step of the Job does not count on, with the reason: the image does not hold it, or
no source of the gate runs it in a Job. So a person sees that a decision was made.

**The image and the checkout.** The runner image holds the runtime of devops-cli and its `review`
extra, and no dev dependency. The implement Job and the model fix of the fix-checks Job run
`bootstrap_checkout` in their checkout before the first agent step: `uv sync --group dev` builds
the venv of the checkout, as the post-create step of the devcontainer does, and npm installs
the Node tools of a root `package-lock.json`. On a new branch, the sync adds `--locked` and npm
runs `npm ci --ignore-scripts`: both refuse a stale lock. On an existing branch, the sync adds
`--frozen` and npm runs `npm install --no-save --ignore-scripts`: both install the lock as it is
and write no tracked file (#6557). A step refuses a dirty worktree, so a stale lock of an existing
branch is the work of the agent: its shell can run `uv lock` or `npm install` and commit the lock.
The stage Job runs in the Service image, which holds no uv, so it runs no bootstrap. The dev
tools (`ToolSource.CHECKOUT`) then come from the venv of the checkout. `checkout_environment` puts `node_modules/.bin` and that venv first on
the PATH of the agent and of the checks that the Job starts. A child that gets a token never gets
it, because the agent can write both folders.

**The uv seed** (#4814). When the Job mounts the uv-seed image volume at `/opt/uv-seed`, and its
`seed.json` holds the uv version, the Python version (`<major>.<minor>`) and the sha256 of the
`uv.lock` of the checkout (the keys `uv`, `python` and `uv_lock_sha256`), the bootstrap copies
`/opt/uv-seed/cache` into the uv cache on the home volume and syncs offline, with no malware check:
CI checked the same hashes when it built the seed. Neither `--locked` nor `--frozen` resolves, so
the seed holds each package that the sync installs. With no seed, or a seed of another lock, the
sync runs online with `UV_HTTP_RETRIES=5`. The Job never needs the seed to start.

The smoke test of the runner image in `ci.yml` and `release.yml` runs
`python -m devops_cli.roadmap.runner_tools` on the built image, which checks the tools of the
image, and `python -m devops_cli.roadmap.runner_tools <checkout>` on a copy of the checkout, which
runs the bootstrap and checks the tools of the checkout. A test in
`tests/roadmap/test_roadmap_runner_tools.py` fails when a program that a `devops ci` row, a hook of
`.pre-commit-config.yaml`, a live-marked test or a required job of `ci.yml` needs is in neither
table.

The module holds no tool version (#5585). The runner image builds FROM the devtools image, which
names the source of each tool, and the `Dockerfile` pins that image by digest (#4361). `uv.lock`
gives the version of each dev dependency. A copy here would be a second pin for each update to
change. Only the project must print a version: the version of its installed distribution, so the
program on PATH is the one of the image venv.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from platformdirs import user_cache_dir

from devops_cli.config.commands import BIN_NPM, BIN_UV
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.output import print_error, print_success
from devops_cli.security.sanitizer import mask_secrets


class ToolSource(StrEnum):
    """Where a Job gets a tool: the base system, the devtools image, the venv of the checkout
    after the bootstrap, or the project in the image venv."""

    BASE = "base"
    DEVTOOLS = "devtools"
    CHECKOUT = "checkout"
    PROJECT = "project"


@dataclass(frozen=True)
class RunnerTool:
    """One program of a Job. `check` is the command that proves it runs; with no `check` the
    program only has to be on PATH. `needed_by` says why the Job needs it: `ci:<row>`, `hook:<id>`,
    `gate:<job>`, `test:<marker>` or `job`."""

    name: str
    source: ToolSource
    needed_by: tuple[str, ...]
    check: tuple[str, ...] = ()


def _checkout(name: str, *needed_by: str) -> RunnerTool:
    return RunnerTool(name, ToolSource.CHECKOUT, needed_by, (name, "--version"))


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
    _checkout("pytest", "ci:test", "ci:bwrap"),
    _checkout("ruff", "ci:lint", "ci:format", "hook:ruff-check", "hook:ruff-format"),
    _checkout("mypy", "ci:typecheck"),
    _checkout("bandit", "ci:security"),
    _checkout("deptry", "ci:deps"),
    _checkout("ast-grep", "ci:constructs", "hook:ast-grep-scan"),
    _checkout("zizmor", "ci:zizmor"),
    _checkout("pre-commit", "job"),
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

# The tools of the image, which the smoke test checks on the built image, and the tools of the
# venv of a checkout, which it checks after the bootstrap of a copy of the checkout.
IMAGE_TOOLS: Final[tuple[RunnerTool, ...]] = tuple(
    tool for tool in RUNNER_TOOLS if tool.source is not ToolSource.CHECKOUT
)
CHECKOUT_TOOLS: Final[tuple[RunnerTool, ...]] = tuple(
    tool for tool in RUNNER_TOOLS if tool.source is ToolSource.CHECKOUT
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
    for the project. The empty string for every other tool, because the devtools image or
    `uv.lock` gives its version."""
    if tool.source is ToolSource.PROJECT:
        return importlib.metadata.version("devops-cli")
    return ""


def tool_failure(tool: RunnerTool, checkout: Path | None = None) -> str | None:
    """Why `tool` fails its check, or None when it is on PATH, its version command exits 0, and the
    project prints its installed version. A tool of the checkout must be in the venv of `checkout`
    (the current folder when None), and its version command runs there with
    `checkout_environment`."""
    texts = MESSAGES.roadmap
    if not tool.check:
        if shutil.which(tool.name) is None:
            return texts.runner_tool_missing.format(tool=tool.name)
        return None
    if tool.source is ToolSource.CHECKOUT:
        root = checkout or Path.cwd()
        if not (root / ".venv" / "bin" / tool.name).is_file():
            return texts.runner_tool_not_in_checkout.format(tool=tool.name, checkout=root)
        done = run_subprocess(list(tool.check), cwd=root, env=checkout_environment(root))
    else:
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


def failures(tools: Sequence[RunnerTool], checkout: Path | None = None) -> list[str]:
    """The failure of each tool of `tools` that fails its check, in the order of the table. A tool
    of the checkout is checked in `checkout`."""
    return [text for tool in tools if (text := tool_failure(tool, checkout)) is not None]


# ── The coder environment of a checkout (#6517) ──────────────────────────────────────────────

# The uv-seed image volume of a Job (#4814): the uv cache that CI filled from `uv.lock`, and
# `seed.json`, the record of what filled it.
UV_SEED_DIR: Final[Path] = Path("/opt/uv-seed")
_SEED_RECORD: Final[str] = "seed.json"
_SEED_CACHE: Final[str] = "cache"
_UV_LOCK: Final[str] = "uv.lock"
_NPM_LOCK: Final[str] = "package-lock.json"
_SYNC: Final[tuple[str, ...]] = (BIN_UV, "sync")
# A new branch refuses a stale lock; an existing branch installs its lock as it is (#6557).
_LOCKED: Final[str] = "--locked"
_FROZEN: Final[str] = "--frozen"
_DEV_GROUP: Final[tuple[str, ...]] = ("--group", "dev")
# The online sync waits out more failed downloads than the 3 of uv; the malware check of uv runs.
_ONLINE: Final[dict[str, str]] = {"UV_HTTP_RETRIES": "5", "UV_MALWARE_CHECK": "1"}
# CI ran the malware check on the hashes of the seed when it built the seed.
_OFFLINE: Final[dict[str, str]] = {"UV_MALWARE_CHECK": "0"}


def checkout_environment(checkout: Path) -> dict[str, str]:
    """The PATH of the agent and of the checks of a Job in `checkout`: `node_modules/.bin` and the
    `bin` folder of the venv of the checkout first, then the PATH of the process. Give it only to
    a child that gets no token: the agent can write both folders."""
    first = (checkout / "node_modules" / ".bin", checkout / ".venv" / "bin")
    rest = os.environ.get("PATH", os.defpath)
    return {"PATH": os.pathsep.join([*(str(folder) for folder in first), rest])}


def _seed_fits(checkout: Path, seed: Path) -> bool:
    """Whether `seed` holds a cache and a record of the uv of the Job, of its Python and of the
    `uv.lock` of `checkout`."""
    record = seed / _SEED_RECORD
    if not ((seed / _SEED_CACHE).is_dir() and record.is_file()):
        return False
    held = json.loads(record.read_text(encoding="utf-8"))
    version = run_subprocess([BIN_UV, "--version"], quiet=True).stdout.split()
    wanted = {
        "uv": version[1] if len(version) > 1 else "",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "uv_lock_sha256": hashlib.sha256((checkout / _UV_LOCK).read_bytes()).hexdigest(),
    }
    return isinstance(held, dict) and wanted.items() <= held.items()


def _run(checkout: Path, argv: Sequence[str], env: dict[str, str] | None = None) -> None:
    """Run one command of the bootstrap in `checkout`. Raises `ToolExecutionError` when it exits
    non-zero or runs out of time."""
    shown = " ".join(argv)
    texts = MESSAGES.roadmap
    limit = load_settings().roadmap.implement.command_timeout_seconds
    try:
        done = run_subprocess(list(argv), cwd=checkout, env=env, quiet=True, timeout=limit)
    except subprocess.TimeoutExpired as exc:
        raise ToolExecutionError(
            texts.implement_stop_program_timeout.format(command=shown, seconds=limit),
            tool_name=argv[0],
        ) from exc
    if done.returncode != 0:
        output = mask_secrets(f"{done.stdout or ''}{done.stderr or ''}").strip()
        raise ToolExecutionError(
            texts.implement_stop_program_failed.format(
                command=shown,
                status=done.returncode,
                output=output[-CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS:],
            ),
            tool_name=argv[0],
            exit_code=done.returncode,
        )


def bootstrap_checkout(checkout: Path, *, locked: bool = True, seed: Path = UV_SEED_DIR) -> None:
    """Build the coder environment of `checkout`, as the module says: the venv of its `uv.lock`
    with the dev group, from the uv seed `seed` when it fits, and the Node packages of its
    `package-lock.json`. With `locked`, for a new branch, the sync refuses a `uv.lock` that does
    not match `pyproject.toml` (`--locked`) and npm runs `npm ci`. Without it, for the checkout of
    an existing branch, the sync installs `uv.lock` as it is (`--frozen`) and npm runs
    `npm install --no-save`, so a stale lock stays as it is and the worktree stays clean (#6557).
    Neither sync resolves, so a seed that fits makes both syncs offline. A checkout with neither
    file gets no command. Raises `ToolExecutionError` when a command fails or runs out of time."""
    if (checkout / _UV_LOCK).is_file():
        sync = (*_SYNC, _LOCKED if locked else _FROZEN, *_DEV_GROUP)
        if _seed_fits(checkout, seed):
            cache = Path(os.environ.get("UV_CACHE_DIR") or user_cache_dir("uv"))
            shutil.copytree(seed / _SEED_CACHE, cache, symlinks=True, dirs_exist_ok=True)
            _run(checkout, (*sync, "--offline"), _OFFLINE)
        else:
            _run(checkout, sync, _ONLINE)
    if (checkout / _NPM_LOCK).is_file():
        npm = ("ci",) if locked else ("install", "--no-save")
        _run(checkout, (BIN_NPM, *npm, "--ignore-scripts"))


def main(argv: Sequence[str] | None = None) -> int:
    """Check every tool of the image. With a checkout, build its coder environment and check every
    tool of the checkout in it. Print each failure. Exit status 1 when any tool or the bootstrap
    fails."""
    parser = argparse.ArgumentParser(prog="python -m devops_cli.roadmap.runner_tools")
    parser.add_argument("checkout", nargs="?", type=Path)
    checkout: Path | None = parser.parse_args(argv).checkout
    tools = IMAGE_TOOLS if checkout is None else CHECKOUT_TOOLS
    if checkout is not None:
        try:
            bootstrap_checkout(checkout)
        except ToolExecutionError as exc:
            print_error(str(exc), prefix=False)
            return 1
    problems = failures(tools, checkout)
    for problem in problems:
        print_error(problem, prefix=False)
    if problems:
        return 1
    print_success(MESSAGES.roadmap.runner_tools_ready.format(count=len(tools)), prefix=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
