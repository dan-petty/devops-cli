"""Invariant: the branch form of the code is the form that the `branch-name` pre-commit hook and
release-please hold (#2337).

`devops repos worktrees add` builds a branch name and reads the issue out of one. The hook refuses
a commit on a branch that breaks the form, and `release-please-config.json` lists the types. When
the three disagree, `add` makes a branch that the hook then refuses.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import CONST_BRANCH_SLUG_PATTERN, CONST_BRANCH_TYPES
from devops_cli.git.branch_form import issue_of_branch, parse_branch
from tests.support.paths import REPO_ROOT


def _branch_name_hook_pattern() -> str:
    """The `--pattern` argument of the `branch-name` hook of `.pre-commit-config.yaml`."""
    config: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks = [
        hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook.get("alias") == "branch-name"
    ]
    assert len(hooks) == 1
    args: list[str] = hooks[0]["args"]
    return args[args.index("--pattern") + 1]


def test_the_branch_types_are_the_types_release_please_lists() -> None:
    config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))

    assert set(CONST_BRANCH_TYPES) == {section["type"] for section in config["changelog-sections"]}


def test_the_branch_form_of_the_code_is_the_form_of_the_hook() -> None:
    types = "|".join(CONST_BRANCH_TYPES)
    form = f"(?:{types})/[0-9]+-{CONST_BRANCH_SLUG_PATTERN}"

    assert _branch_name_hook_pattern() == f"^(?!{form}$)"


def test_a_branch_gives_its_type_issue_and_slug() -> None:
    parts = parse_branch("feat/2657-staged-takeover")

    assert parts is not None
    assert (parts.type, parts.issue, parts.slug) == ("feat", 2657, "staged-takeover")


@pytest.mark.parametrize("branch", [None, "main", "feat/2657", "wip/2657-x", "feat/2657-Bad"])
def test_a_branch_that_breaks_the_form_has_no_parts(branch: str | None) -> None:
    assert parse_branch(branch) is None
    assert issue_of_branch(branch) is None
