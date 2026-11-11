"""The definition check that the stage probe and the implement job share (#3417)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.premise import added_guard, definition_lines
from devops_cli.roadmap.refine.refine import git_result
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.roadmap_stage import StageRepo


def test_the_definition_lines_of_an_identifier_come_from_the_commit() -> None:
    lines = definition_lines(REPO_ROOT, "HEAD", "_delivery_title") or ()

    assert any(
        line.startswith("HEAD:src/devops_cli/roadmap/implement/implement_run.py:")
        and "_delivery_title" in line
        for line in lines
    )


@pytest.mark.parametrize(
    ("task", "name"),
    [
        (
            "- [ ] 1.2 Add the guard `_delivery_title` to `src/devops_cli/shout.py`",
            "_delivery_title",
        ),
        ("- [ ] 1.2 Create a check `title_ok` in `src/devops_cli/shout.py`", "title_ok"),
        ("- [ ] 1.2 Add `shout` to `src/devops_cli/shout.py`", None),
        ("- [ ] 1.2 Change the guard `_delivery_title` in `src/devops_cli/shout.py`", None),
        ("- [ ] 1.2 Add the guard `one` and the check `two`", None),
        ("- [ ] 1.1 Add the failing test `test_title_check` for `src/devops_cli/shout.py`", None),
        ("- [ ] 1.2 Add a guard to `run_step` that refuses an empty plan", None),
        ("- [ ] 1.2 Add a check in `_return_premise` for a blank title", None),
        ("- [ ] 1.2 Add a check to `apply_return` that reads the item", None),
        ("- [ ] 1.2 Create a check named `title_ok` in `src/devops_cli/shout.py`", "title_ok"),
    ],
)
def test_a_task_adds_a_guard_only_when_the_identifier_follows_the_guard_word(
    task: str, name: str | None
) -> None:
    assert added_guard(task) == name


SCOUT = "src/scout.rs"
SCOUT_SOURCE = (
    "use crate::map::Grid;\n"
    "\n"
    "#[test]\n"
    "fn scout_reaches_target() {\n"
    "    assert!(Grid::new().reaches());\n"
    "}\n"
)
MAIN = "src/main.rs"
MAIN_SOURCE = "fn main() {\n    scout_reaches_target();\n}\n"
DEPLOY = "scripts/deploy.sh"
DEPLOY_SOURCE = "#!/bin/sh\nsetup_node() {\n  echo ready\n}\nsetup_node\n"


def _head(repo: StageRepo, files: dict[str, str]) -> str:
    repo.track(files)
    return repo.git("rev-parse", "HEAD")


def test_a_rust_function_is_defined_on_its_fn_line(stage_repo: StageRepo) -> None:
    sha = _head(stage_repo, {SCOUT: SCOUT_SOURCE, MAIN: MAIN_SOURCE})

    lines = definition_lines(stage_repo.clone, sha, "scout_reaches_target")

    assert lines == (f"{sha}:{SCOUT}:4:fn scout_reaches_target() {{",)


def test_a_shell_function_is_defined_on_its_line(stage_repo: StageRepo) -> None:
    sha = _head(stage_repo, {DEPLOY: DEPLOY_SOURCE})

    lines = definition_lines(stage_repo.clone, sha, "setup_node")

    assert lines == (f"{sha}:{DEPLOY}:2:setup_node() {{",)


def test_a_call_and_a_heading_are_no_definition(stage_repo: StageRepo) -> None:
    sha = _head(stage_repo, {MAIN: MAIN_SOURCE, "README.md": "## scout_reaches_target\n"})

    assert definition_lines(stage_repo.clone, sha, "scout_reaches_target") == ()


def test_a_python_definition_needs_one_command(stage_repo: StageRepo) -> None:
    sha = _head(
        stage_repo, {"src/scout.py": "def scout_reaches_target():\n    pass\n", SCOUT: SCOUT_SOURCE}
    )
    ran: list[tuple[str, ...]] = []

    def spy(checkout: Path, *args: str) -> tuple[int, str]:
        ran.append(args)
        return git_result(checkout, *args)

    lines = definition_lines(stage_repo.clone, sha, "scout_reaches_target", spy, commands=1)

    assert (lines, len(ran)) == ((f"{sha}:src/scout.py:1:def scout_reaches_target():",), 1)


def test_one_command_leaves_a_name_of_another_language_undecided(stage_repo: StageRepo) -> None:
    sha = _head(stage_repo, {SCOUT: SCOUT_SOURCE})

    lines = definition_lines(stage_repo.clone, sha, "scout_reaches_target", commands=1)

    assert lines is None
