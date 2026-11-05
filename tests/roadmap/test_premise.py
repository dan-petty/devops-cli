"""The definition check that the stage probe and the implement job share (#3417)."""

from __future__ import annotations

from tests.support.paths import REPO_ROOT


def test_the_definition_lines_of_an_identifier_come_from_the_commit() -> None:
    from devops_cli.roadmap.premise import definition_lines

    lines = definition_lines(REPO_ROOT, "HEAD", "_delivery_title")

    assert any(
        line.startswith("HEAD:src/devops_cli/roadmap/implement_run.py:")
        and "_delivery_title" in line
        for line in lines
    )
