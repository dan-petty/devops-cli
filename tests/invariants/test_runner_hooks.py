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
from devops_cli.roadmap.runner_tools import tool_names
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
    """A local hook that starts with `uv run` runs a dev dependency of the lock (the `runner` stage
    syncs the dev group) or the `devops` script. Any other local hook starts a program that the
    runner image holds (`RUNNER_TOOLS`), as `sh` for `branch-current` (#4670). A hook under
    coreutils `timeout` runs `timeout`, and the command after its limit is checked the same way
    (#4775). A hook that needs another program fails here until the image holds the program
    (#3072)."""
    provided = _dev_dependencies() | {"devops"}
    image = set(tool_names())
    unsupported = []
    for hook in _local_hooks():
        words = shlex.split(str(hook["entry"]))
        if words[0] == "timeout":
            unsupported += [] if "timeout" in image else [(hook["id"], "timeout")]
            words = words[2:]
        if words[:2] == ["uv", "run"]:
            tool = words[2] if len(words) > 2 else ""
            held = PROVIDERS.get(tool) in provided
        else:
            tool = words[0]
            held = tool in image
        if not held:
            unsupported.append((hook["id"], tool))
    assert unsupported == []


def test_the_runner_image_installs_the_dev_group_and_holds_openspec() -> None:
    """`pre-commit` and `ast-grep` come with the dev group, which `runner-deps` installs from the
    dev requirements of the `lock` stage. The OpenSpec gate needs the pinned `openspec` that the
    builder stage installs: `runner-tools` builds on the builder, and `runner-deps` copies its
    tool directory."""
    dockerfile = stages((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    runner_deps = [" ".join(words) for words in dockerfile["runner-deps"]]
    builder = [" ".join(words) for words in dockerfile["builder"]]
    lock = " ".join(" ".join(words) for words in dockerfile["lock"])
    assert dockerfile["runner"][0][1] == "runner-deps"
    assert any("uv pip install" in line and "/lock/dev.txt" in line for line in runner_deps)
    assert "--only-dev" in lock.split()
    assert any("install-tools" in line and "--tool openspec" in line for line in builder)
    assert dockerfile["runner-tools"][0][1] == "builder"
    assert "COPY --from=runner-tools /opt/devops-tools /opt/devops-tools" in runner_deps
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
