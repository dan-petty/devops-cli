"""The hooks of the repository run in the runner Job as they run in the devcontainer (#3043).

The Job runs the stages of `.pre-commit-config.yaml` with `pre-commit run`. So each local hook must
run with what the runner image holds, the checks that the Job adds must be rows of `devops ci`, and
the branches that the Job makes must pass the branch-name hook. These tests read the files and fail
when one of them drifts from the others.
"""

from __future__ import annotations

import re
import shlex
import tomllib
from typing import Any

import yaml

from devops_cli.git.branch_form import branch_name
from tests.support.dockerfile import stages
from tests.support.paths import REPO_ROOT as ROOT

CONFIG = ROOT / ".pre-commit-config.yaml"
# The tool that a `uv run` hook starts, and the dev dependency or script that provides it.
PROVIDERS = {"ast-grep": "ast-grep-cli", "devops": "devops"}
TYPES = (
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "docs",
    "test",
    "build",
    "ci",
    "style",
    "chore",
)


def _hooks() -> list[dict[str, Any]]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return [hook for repo in config["repos"] for hook in repo.get("hooks", [])]


def _local_hooks() -> list[dict[str, Any]]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return [hook for repo in config["repos"] if repo["repo"] == "local" for hook in repo["hooks"]]


def _dev_dependencies() -> set[str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {
        re.split(r"[=<>~!\[ ]", requirement, maxsplit=1)[0]
        for requirement in pyproject["dependency-groups"]["dev"]
    }


def test_every_local_hook_runs_a_tool_that_the_runner_image_holds() -> None:
    """A local hook starts with `uv run`, and its tool is a dev dependency of the lock (the
    `runner` stage syncs the dev group) or the `devops` script. A hook that needs another program
    fails here until the image holds the program (#3072)."""
    provided = _dev_dependencies() | {"devops"}
    unsupported = []
    for hook in _local_hooks():
        words = shlex.split(str(hook["entry"]))
        tool = words[2] if words[:2] == ["uv", "run"] and len(words) > 2 else words[0]
        if words[:2] != ["uv", "run"] or PROVIDERS.get(tool) not in provided:
            unsupported.append((hook["id"], tool))
    assert unsupported == []


def test_the_runner_stage_syncs_the_dev_group_and_holds_openspec() -> None:
    """`pre-commit` and `ast-grep` come with the dev group, and the OpenSpec gate needs the pinned
    `openspec` that the builder stage installs and the runner stage inherits."""
    dockerfile = stages((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    runner = [" ".join(words) for words in dockerfile["runner"]]
    builder = [" ".join(words) for words in dockerfile["builder"]]
    assert runner[0] == "FROM builder AS runner"
    sync = [line for line in runner if "uv sync --locked" in line]
    assert sync != []
    assert all("--no-dev" not in line for line in sync)
    assert any("install-tools" in line and "--tool openspec" in line for line in builder)
    assert {"pre-commit", "ast-grep-cli"} <= _dev_dependencies()


def test_the_branch_name_hook_accepts_a_branch_of_every_type_that_the_job_makes() -> None:
    """The Job makes `<type>/<issue>-<slug>` with `branch_name`. The hook refuses a name that its
    pattern does not match, so a type that the hook lacks would stop every commit."""
    hook = next(hook for hook in _hooks() if hook.get("alias") == "branch-name")
    pattern = re.compile(str(hook["args"][hook["args"].index("--pattern") + 1]))
    made = [branch_name(3043, kind, "runner-hooks") for kind in TYPES]
    assert [name for name in made if pattern.match(name)] == []
    assert pattern.match("scratch/work") is not None


def test_the_main_branch_guard_does_not_refuse_the_branch_of_an_item() -> None:
    guard = next(hook for hook in _hooks() if hook["id"] == "no-commit-to-branch")
    assert guard["args"] == ["--branch", "main"]
    assert "main" != branch_name(3043, "feat", "runner-hooks")
