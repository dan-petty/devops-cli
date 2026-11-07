"""The requirement lines of an issue, which the plan must map to its groups (#3253).

The plan check mapped only the acceptance criteria, so a plan could drop a named caller, a path, a
command or a decision of the issue. `requirement_lines` reads the bullets of the sections that a
person wrote, the backticked paths and `devops` commands of its text, and each `Decision:` line,
and gives each one an ID in source order.
"""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_criteria import RequirementLine, requirement_lines

BODY = """### What should happen

- The stage job calls `devops pr ready` after the checks pass.

### Design

The change edits `src/devops_cli/roadmap/stage/stage_criteria.py`.

Decision: Keep the IDs in source order.

### Acceptance criteria

- [ ] A test shows that the plan maps every line.

<!-- devops-roadmap-refine:start -->
## Proposed design

### What should happen

- A bullet of the refine block is no requirement of the issue.

<!-- devops-roadmap-refine:end -->
"""


def test_the_requirement_lines_hold_a_command_a_path_and_a_decision() -> None:
    lines = requirement_lines(BODY)

    assert [line.id for line in lines] == ["REQ-001", "REQ-002", "REQ-003"]
    assert [line.kind for line in lines] == ["command", "path", "decision"]
    assert [line.text for line in lines] == [
        "devops pr ready",
        "src/devops_cli/roadmap/stage/stage_criteria.py",
        "Decision: Keep the IDs in source order.",
    ]
    assert [line.source_line for line in lines] == [3, 7, 9]


def test_the_items_of_the_acceptance_criteria_and_the_refine_block_are_left_out() -> None:
    texts = [line.text for line in requirement_lines(BODY)]

    assert not any("maps every line" in text for text in texts)
    assert not any("refine block" in text for text in texts)


def test_a_bullet_with_no_literal_is_a_requirement_line_of_its_own() -> None:
    body = "### What should happen\n\n- The row checks at most 20 items a round.\n"

    lines = requirement_lines(body)

    assert [(line.id, line.kind, line.text) for line in lines] == [
        ("REQ-001", "bullet", "The row checks at most 20 items a round.")
    ]


def test_a_body_with_no_requirement_line_has_none() -> None:
    assert requirement_lines("") == []
    assert requirement_lines("### What happened\n\nA plan dropped a caller.\n") == []


def test_the_line_of_a_requirement_is_the_line_of_the_body() -> None:
    line = requirement_lines(BODY)[0]

    assert isinstance(line, RequirementLine)
    assert line.model_dump() == {
        "id": "REQ-001",
        "kind": "command",
        "text": "devops pr ready",
        "source_line": 3,
    }
