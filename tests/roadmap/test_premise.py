"""The definition check that the stage probe and the implement job share (#3417)."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.premise import added_guard
from tests.support.paths import REPO_ROOT


def test_the_definition_lines_of_an_identifier_come_from_the_commit() -> None:
    from devops_cli.roadmap.premise import definition_lines

    lines = definition_lines(REPO_ROOT, "HEAD", "_delivery_title")

    assert any(
        line.startswith("HEAD:src/devops_cli/roadmap/implement_run.py:")
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
