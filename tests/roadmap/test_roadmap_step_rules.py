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
    Route,
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


def test_a_route_without_sections_gives_the_start_of_its_document_cut_to_the_cap(
    tmp_path: Path,
) -> None:
    """No route of `ROUTES` has no sections since the OpenTofu guide moved to infra (#6679), so
    the route and its document over the cap are built here."""
    document = "# Guide\n\n" + "Apply the module. " * 40_000
    (tmp_path / "GUIDE.md").write_text(document, encoding="utf-8")
    route = Route(row="change a module", patterns=("modules/**",), document="GUIDE.md")

    text = route_text(tmp_path, route)

    assert (
        text.startswith(document[:40]),
        TRUNCATED in text,
        count_tokens(text) <= CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS + 8,
    ) == (True, True, True)


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


def test_a_group_that_names_only_a_manifest_gets_no_testing_document() -> None:
    group = _group("k8s/llm/sample.yaml")

    assert (_documents(group), "## Image Pins" in rules_sections(REPO_ROOT, group)[-1]) == (
        ["k8s/README.md", "docs/CLUSTER.md"],
        True,
    )


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
    assert _documents(_group("src/devops_cli/roadmap/stage/stage.py")) == [
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
    """A checkout with no `AGENTS.md` gets no section of its rules: the generic rules stand in
    under their own heading (#4650)."""
    sections = rules_sections(tmp_path, _group("tests/test_sample.py"))

    assert [section for section in sections if section.startswith(f"# {RULES_HEADING}")] == []


def test_a_checkout_without_agents_md_gets_the_generic_rules(tmp_path: Path) -> None:
    sections = rules_sections(tmp_path, _group("tests/test_sample.py"))

    assert len(sections) == 1

    from devops_cli.roadmap.step_rules import GENERIC_RULES_HEADING

    assert _headings(sections) == [f"# {GENERIC_RULES_HEADING}"]


def test_a_checkout_without_agents_md_keeps_its_routed_sections(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "TESTING.md").write_text(
        "## Conventions\n\n### Doubles\n\nText.\n", encoding="utf-8"
    )

    headings = _headings(rules_sections(tmp_path, _group("tests/test_sample.py")))

    assert len(headings) == 2

    from devops_cli.roadmap.step_rules import GENERIC_RULES_HEADING

    assert headings == [f"# {GENERIC_RULES_HEADING}", route_heading("docs/TESTING.md")]


def test_the_generic_rules_name_no_python_without_a_python_manifest(tmp_path: Path) -> None:
    sections = rules_sections(tmp_path, _group("tests/test_sample.py"))

    assert len(sections) == 1
    assert [line for line in sections[0].splitlines() if "Python" in line] == []


def test_a_routed_document_that_the_checkout_lacks_adds_no_section(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Rules\n\nBe brief.\n", encoding="utf-8")

    assert _headings(rules_sections(tmp_path, _group("tests/test_sample.py"))) == [
        f"# {RULES_HEADING}"
    ]


def test_an_agents_md_over_the_cap_is_cut_to_the_cap(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Rule. " * 40_000, encoding="utf-8")

    [section] = rules_sections(tmp_path, _group())

    assert (
        count_tokens(section)
        <= CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS + count_tokens(RULES_HEADING) + 8,
        TRUNCATED in section,
    ) == (True, True)


def test_an_agents_md_under_the_cap_is_not_cut() -> None:
    [section, *_] = rules_sections(REPO_ROOT, _group())

    assert TRUNCATED not in section


def test_the_preset_holds_no_shell_table() -> None:
    """#6527: a toolchain preset holds no shell allowlist, local command, or refusal table."""
    from devops_cli.roadmap.toolchains import DEVOPS_CLI_PRESET, NEUTRAL_PRESET

    for preset in (DEVOPS_CLI_PRESET, NEUTRAL_PRESET):
        assert not hasattr(preset, "shell_programs")
        assert not hasattr(preset, "local_commands")
        assert not hasattr(preset, "refusals")
    joined = "\n".join(rules_sections(REPO_ROOT, _group("src/devops_cli/roadmap/step.py")))
    assert "{{shell_programs}}" not in joined
    assert "SHELL_PROGRAMS" not in joined
