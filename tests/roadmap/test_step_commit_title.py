"""The title of an intermediate implementation step commit (#3351)."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.step_commit import step_commit_title


@pytest.mark.parametrize(
    ("item_title", "step_title", "item", "title"),
    [
        (
            "docs(security): SECURITY.md says that the Valkey commands are not MCP tools",
            "Correct the Valkey paragraph in SECURITY.md",
            2670,
            "docs(security): Correct the Valkey paragraph in SECURITY.md (#2670)",
        ),
        (
            "docs(security): SECURITY.md says that the Valkey commands are not MCP tools",
            "Correct the Valkey paragraph in SECURITY.md (#2670)",
            2670,
            "docs(security): Correct the Valkey paragraph in SECURITY.md (#2670)",
        ),
        (
            "Correct the Valkey paragraph",
            "Update SECURITY.md",
            2670,
            "chore: Update SECURITY.md (#2670)",
        ),
        ("fix(k8s)!: drop a flag", "Drop the flag", 7, "fix(k8s): Drop the flag (#7)"),
        ("chore: update a pin", "Bump the pin", 8, "chore: Bump the pin (#8)"),
    ],
)
def test_a_step_commit_title_holds_the_type_and_the_scope_of_the_item_once(
    item_title: str, step_title: str, item: int, title: str
) -> None:
    assert step_commit_title(item_title, step_title, item) == title
