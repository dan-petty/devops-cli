"""The prompt of the implement step names the section of the rules and the tools that the code
gives it (#3006, #3097)."""

from __future__ import annotations

from devops_cli.ai.task_loader import load_task_prompt

PROMPT = "roadmap_implement_step.md"


def test_the_prompt_names_the_section_that_holds_the_rules() -> None:
    from devops_cli.roadmap.step_rules import RULES_HEADING

    prompt = load_task_prompt(PROMPT)

    assert f'"{RULES_HEADING}"' in prompt


def test_the_rendered_prompt_names_create_directory_and_holds_no_python_mkdir() -> None:
    from devops_cli.roadmap.implement.implement_step import step_instructions

    rendered = step_instructions()

    assert "create_directory" in rendered
    assert not any(
        "python" in line and "-c" in line and "mkdir" in line for line in rendered.splitlines()
    )


def test_the_tools_table_lists_the_registry_tools() -> None:
    from devops_cli.roadmap.implement.implement_step import step_instructions
    from devops_cli.roadmap.tools import HOLDER_IMPLEMENT, TOOLS, tool_names

    prompt = step_instructions()
    for name in tool_names(HOLDER_IMPLEMENT):
        entry = TOOLS[name]
        access = "read" if entry.read_only else "write"
        assert f"| `{name}` | {access} | {entry.purpose} |" in prompt
