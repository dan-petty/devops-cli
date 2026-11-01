"""The rules a step reads for a group (#3097): `AGENTS.md` of the checkout, and the sections of the
documents that `AGENTS.md` routes the group to.

The routes are tested against the real "Where to look" table of this repository, so a table that
drifts from the code fails here. The sections are read from the real documents.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.roadmap.step_files import TaskGroup, parse_task_groups, section_text
from devops_cli.roadmap.step_rules import (
    ROUTES,
    RULES_HEADING,
    route_heading,
    route_text,
    rules_sections,
)
from tests.support.markdown_tables import where_to_look
from tests.support.paths import REPO_ROOT

AGENTS_MD = REPO_ROOT / "AGENTS.md"
TRUNCATED = "[truncated due to context budget]"


def _group(*paths: str) -> TaskGroup:
    """A group whose one task names `paths` in code spans."""
    spans = " and ".join(f"`{path}`" for path in paths)
    [group] = parse_task_groups(f"## 1. A group\n\n- [ ] 1.1 Change {spans}\n")
    return group


def _headings(sections: list[str]) -> list[str]:
    return [section.splitlines()[0] for section in sections]


def _documents(group: TaskGroup, source: Path = REPO_ROOT) -> list[str]:
    """The routed documents of the sections that a group gets, after `AGENTS.md`."""
    return [heading.split(" ")[1] for heading in _headings(rules_sections(source, group))[1:]]


# ── The table of routes against AGENTS.md ─────────────────────────────────────────────────


def test_each_route_names_a_row_of_the_where_to_look_table_that_links_its_document() -> None:
    rows = where_to_look(AGENTS_MD)

    assert [
        route.document for route in ROUTES if route.document not in rows.get(route.row, [])
    ] == []


def test_each_route_names_a_document_and_sections_that_exist() -> None:
    missing = [
        (route.document, title)
        for route in ROUTES
        for title in route.sections
        if not (REPO_ROOT / route.document).is_file()
        or not section_text(
            (REPO_ROOT / route.document).read_text(encoding="utf-8"), frozenset({title.casefold()})
        )
    ]

    assert missing == []


def test_the_sections_of_a_route_fit_the_cap_and_are_not_cut() -> None:
    texts = {route.document: route_text(REPO_ROOT, route) for route in ROUTES}

    assert [document for document, text in texts.items() if not text] == []
    assert [
        d
        for d, text in texts.items()
        if count_tokens(text) > CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
    ] == []
    assert [document for document, text in texts.items() if TRUNCATED in text] == []


def test_a_route_without_sections_gives_the_start_of_its_document_cut_to_the_cap() -> None:
    [route] = [route for route in ROUTES if not route.sections]

    text = route_text(REPO_ROOT, route)

    assert text.startswith((REPO_ROOT / route.document).read_text(encoding="utf-8")[:40])
    assert count_tokens(text) <= CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS


# ── The sections of a group ───────────────────────────────────────────────────────────────


def test_the_first_section_is_agents_md_verbatim_under_its_heading() -> None:
    sections = rules_sections(REPO_ROOT, _group("src/devops_cli/sample.py"))

    assert sections[0] == f"# {RULES_HEADING}\n\n{AGENTS_MD.read_text(encoding='utf-8').strip()}"


@pytest.mark.parametrize(
    "named",
    ["tests/test_sample.py", "tests/roadmap/test_not_yet_written.py::test_name"],
    ids=["a test file", "a new test file with a test name"],
)
def test_a_group_that_names_a_test_file_gets_the_testing_document(named: str) -> None:
    group = _group(named)

    assert _documents(group) == ["docs/TESTING.md"]


def test_the_testing_sections_hold_the_text_of_the_document() -> None:
    sections = rules_sections(REPO_ROOT, _group("tests/test_sample.py"))

    assert "### Doubles" in sections[1]


def test_a_group_that_names_only_a_manifest_gets_no_testing_document() -> None:
    documents = _documents(_group("k8s/llm/sample.yaml"))

    assert documents == ["k8s/README.md"]


def test_a_group_that_changes_source_gets_the_standards_and_the_contributing_guide() -> None:
    documents = _documents(_group("src/devops_cli/commands/sample.py", "tests/test_sample.py"))

    assert documents == ["docs/TESTING.md", "ARCHITECTURE.md", "CONTRIBUTING.md"]


def test_a_group_that_changes_security_code_gets_the_security_policy() -> None:
    assert _documents(_group("src/devops_cli/security/sanitizer.py")) == [
        "ARCHITECTURE.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
    ]


def test_a_group_that_changes_roadmap_code_gets_the_roadmap_workflow() -> None:
    assert _documents(_group("src/devops_cli/roadmap/stage.py")) == [
        "ARCHITECTURE.md",
        "CONTRIBUTING.md",
        "docs/ROADMAP_WORKFLOW.md",
    ]


def test_a_group_that_names_only_a_document_gets_only_agents_md() -> None:
    sections = rules_sections(REPO_ROOT, _group("docs/SAMPLE.md"))

    assert _headings(sections) == [f"# {RULES_HEADING}"]


def test_a_group_with_no_path_gets_only_agents_md() -> None:
    [group] = parse_task_groups("## 1. A group\n\n- [ ] 1.1 Make the check pass\n")

    assert _headings(rules_sections(REPO_ROOT, group)) == [f"# {RULES_HEADING}"]


def test_a_routed_section_has_the_heading_of_its_document() -> None:
    sections = rules_sections(REPO_ROOT, _group("tests/test_sample.py"))

    assert _headings(sections)[1] == route_heading("docs/TESTING.md")


def test_a_checkout_without_agents_md_gets_no_section(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "TESTING.md").write_text("## Conventions\n\n### Doubles\n\nText.\n")

    assert rules_sections(tmp_path, _group("tests/test_sample.py")) == []


def test_a_routed_document_that_the_checkout_lacks_adds_no_section(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Rules\n\nBe brief.\n", encoding="utf-8")

    assert _headings(rules_sections(tmp_path, _group("tests/test_sample.py"))) == [
        f"# {RULES_HEADING}"
    ]
