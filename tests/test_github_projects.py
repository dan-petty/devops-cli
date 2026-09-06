"""Test suite for GitHub Projects v2 schema, views, and task synchronization."""

from __future__ import annotations

from pathlib import Path

from devops_cli.github.projects import (
    ProjectTemplate,
    load_project_template,
    parse_tasks_to_project_items,
)


def test_load_project_template() -> None:
    """ProjectTemplate properly parses the declarative template schema."""
    template_path = Path(".github/project-template.json")
    assert template_path.exists()

    template = load_project_template(template_path)
    assert isinstance(template, ProjectTemplate)
    assert "DevOps CLI" in template.name
    assert len(template.fields) >= 4
    assert len(template.views) == 4

    view_names = [v.name for v in template.views]
    assert "Sprint Kanban" in view_names
    assert "Roadmap Timeline" in view_names
    assert "Triage & Quality Table" in view_names
    assert "Value vs Effort Priority Matrix" in view_names


def test_parse_tasks_to_project_items(tmp_path: Path) -> None:
    """parse_tasks_to_project_items converts task.md lines into ProjectItem models."""
    sample_task_md = tmp_path / "task.md"
    sample_task_md.write_text(
        "# Task Tracking\n\n"
        "### Completed Tasks\n"
        "- [x] Phase 1: Baseline CI run\n\n"
        "### In-Progress Tasks (WIP)\n"
        "- [ ] Phase 2: Active feature work\n\n"
        "### Pending Tasks\n"
        "- [ ] Phase 3: Future item\n",
        encoding="utf-8",
    )

    items = parse_tasks_to_project_items(sample_task_md)
    assert len(items) == 3
    assert items[0].title == "Phase 1: Baseline CI run"
    assert items[0].status == "Done"

    assert items[1].title == "Phase 2: Active feature work"
    assert items[1].status == "In Progress"

    assert items[2].title == "Phase 3: Future item"
    assert items[2].status == "Backlog"
