"""Offline test suite asserting claims made in AGENTS.md and related documentation."""

from __future__ import annotations

import json
import re
from itertools import pairwise
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin

from devops_cli.ai.instruction_generator import (
    POINTER_STUBS,
    generate_instruction_content,
    parse_project_metadata,
)
from devops_cli.ai.personas import Persona
from devops_cli.config.constants import CONST_AGENTS_MD_MAX_CHARS
from tests.support.paths import REPO_ROOT


def _extract_issue_templates(agents_md_content: str) -> set[str]:
    """Extract all issue template filenames referenced under .github/ISSUE_TEMPLATE/ in AGENTS.md."""
    templates = set(
        re.findall(r"\.github/ISSUE_TEMPLATE/([a-zA-Z0-9_\-]+\.ya?ml)", agents_md_content)
    )
    for line in agents_md_content.splitlines():
        if ".github/ISSUE_TEMPLATE/" in line:
            for fname in re.findall(r"`([a-zA-Z0-9_\-]+\.ya?ml)`", line):
                templates.add(fname)
    return templates


def test_issue_templates_named_in_agents_md_exist() -> None:
    """Every .github/ISSUE_TEMPLATE/*.yml named in AGENTS.md must exist on disk."""
    agents_path = REPO_ROOT / "AGENTS.md"
    assert agents_path.is_file(), "AGENTS.md must exist at repo root"

    templates = _extract_issue_templates(agents_path.read_text(encoding="utf-8"))
    assert len(templates) > 0, "AGENTS.md must reference at least one issue template"

    template_dir = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
    missing = [t for t in templates if not (template_dir / t).is_file()]
    assert not missing, f"Missing issue templates referenced in AGENTS.md: {missing}"

    # Also assert that deprecated/unsupported templates are not referenced
    assert "security_advisory.yml" not in templates and "task.yml" not in templates, (
        "Deprecated templates must not be referenced in AGENTS.md"
    )


def test_personas_in_self_improvement_are_valid() -> None:
    """Every persona listed as active in docs/SELF_IMPROVEMENT.md is a Persona enum value."""
    doc_path = REPO_ROOT / "docs" / "SELF_IMPROVEMENT.md"
    assert doc_path.is_file(), "docs/SELF_IMPROVEMENT.md must exist"

    content = doc_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # The line 187 negation of performance/sre is accepted and must be the only reference
    negation_lines = [
        line for line in lines if "performance" in line.lower() or "sre" in line.lower()
    ]
    assert len(negation_lines) == 1, (
        f"Expected exactly 1 line referencing performance/sre, found {len(negation_lines)}"
    )
    assert "no `performance` or `sre` persona" in negation_lines[0], (
        "Reference to performance/sre must be the explicit non-existence negation"
    )

    valid_enum_values = {p.value for p in Persona}
    active_personas: set[str] = set()
    for line in lines:
        if line in negation_lines:
            continue
        if "persona" in line.lower():
            for word in re.findall(r"\b([a-zA-Z]+)\b", line):
                if word.lower() in valid_enum_values:
                    active_personas.add(word.lower())

    assert active_personas == valid_enum_values, (
        f"Active personas in docs ({active_personas}) must match Persona enum values ({valid_enum_values})"
    )


def test_instruction_stubs_byte_equal_to_generator() -> None:
    """The pointer stubs must match generator output byte-for-byte."""
    meta = parse_project_metadata(REPO_ROOT)
    for target in ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md"):
        expected = generate_instruction_content(target, meta)
        actual = (REPO_ROOT / target).read_text(encoding="utf-8")
        assert actual == expected, f"{target} differs from generator output"


def test_the_canonical_source_note_links_every_pointer_stub() -> None:
    """The Canonical Source note of AGENTS.md, and of the generated one, links each pointer stub."""
    meta = parse_project_metadata(REPO_ROOT)
    documents = (
        (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"),
        generate_instruction_content("AGENTS.md", meta),
    )
    for document in documents:
        note = document.split("**Canonical Source**", 1)[1].split("\n\n", 1)[0]
        assert [stub for stub in POINTER_STUBS if f"[{stub}](./{stub})" not in note] == []


def test_agents_md_stays_within_character_budget() -> None:
    """AGENTS.md must fit within the context budget constant, which cannot exceed 40,000 chars."""
    assert (
        CONST_AGENTS_MD_MAX_CHARS <= 40_000,
        len((REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")) <= CONST_AGENTS_MD_MAX_CHARS,
    ) == (True, True)


# ── The test conventions and the documents that point to them (#1308) ───────────────────────

_TESTING_MD = REPO_ROOT / "docs" / "TESTING.md"
_TESTS_ADR = REPO_ROOT / "docs" / "adr" / "0007-tests-double-only-process-edges.md"
# The documents that each stated test rules of their own, and link docs/TESTING.md instead.
_DOCUMENTS_POINTING_AT_TESTING_MD = (
    "AGENTS.md",
    "CONTRIBUTING.md",
    "docs/SDLC.md",
    "docs/ROUTINE_TASKS.md",
    "docs/SELF_IMPROVEMENT.md",
    "src/devops_cli/ai/knowledge_base/it_domains/tools/ruff_mypy_pytest.md",
    "src/devops_cli/ai/knowledge_base/it_domains/topics/continuous_integration_and_progressive_verification.md",
    "src/devops_cli/ai/knowledge_base/devops_cli/libraries/ruff_mypy_pytest.md",
)
# CommonMark, with each heading given the id GitHub gives it, so a `#fragment` can be resolved.
_MARKDOWN = MarkdownIt("commonmark").use(anchors_plugin, max_level=6)


def _hrefs(document: Path) -> list[str]:
    """The target of every link in the document, as CommonMark reads it."""
    return [
        str(token.attrs["href"])
        for block in _MARKDOWN.parse(document.read_text(encoding="utf-8"))
        for token in block.children or ()
        if token.type == "link_open"
    ]


def _relative_links(document: Path) -> dict[str, tuple[Path, str]]:
    """Each relative link in the document, with the file it names and its fragment.

    A bare `#fragment` names the document itself. A link with a scheme or a host names another
    site and is left out.
    """
    return {
        href: (
            (document.parent / unquote(parts.path)).resolve() if parts.path else document,
            unquote(parts.fragment),
        )
        for href, parts in ((href, urlsplit(href)) for href in _hrefs(document))
        if not (parts.scheme or parts.netloc)
    }


def _heading_ids(document: Path) -> set[str]:
    """The id GitHub gives each heading of the Markdown document."""
    return {
        str(token.attrs["id"])
        for token in _MARKDOWN.parse(document.read_text(encoding="utf-8"))
        if token.type == "heading_open"
    }


def _broken_links(document: Path) -> list[str]:
    """Each relative link in the document whose file is missing, or whose fragment names no
    heading of the Markdown file it points at."""
    return [
        href
        for href, (target, fragment) in _relative_links(document).items()
        if not target.exists()
        or (fragment and target.suffix == ".md" and fragment not in _heading_ids(target))
    ]


def test_every_document_that_stated_test_rules_links_testing_md() -> None:
    """AGENTS.md, the contributor guides, the review conventions and the knowledge base each
    stated test rules of their own, and several contradicted the conventions the owner decided
    on 2026-10-07. Each links `docs/TESTING.md` in their place (#1308)."""
    unlinked = [
        name
        for name in _DOCUMENTS_POINTING_AT_TESTING_MD
        if _TESTING_MD not in {target for target, _ in _relative_links(REPO_ROOT / name).values()}
    ]

    assert unlinked == []


def test_every_relative_link_in_the_test_conventions_and_their_pointers_resolves() -> None:
    """A renumbered ADR or a moved document leaves no dead link in the test conventions, their
    ADR or a document that points to them (#1308)."""
    documents = {
        "docs/TESTING.md": _TESTING_MD,
        "docs/adr/0007-tests-double-only-process-edges.md": _TESTS_ADR,
        **{name: REPO_ROOT / name for name in _DOCUMENTS_POINTING_AT_TESTING_MD},
    }

    broken = {
        name: links
        for name, path in documents.items()
        if (links := _broken_links(path) if path.is_file() else ["<missing>"])
    }

    assert broken == {}


def test_a_link_to_a_missing_file_or_heading_is_broken(tmp_path: Path) -> None:
    """Negative control: the check reports a link to a missing file or to a missing heading, and
    passes links to an existing heading, one with letters outside ASCII included, to the
    document's own heading and to another site."""
    (tmp_path / "other.md").write_text(
        "# Other\n\n## Kept heading\n\n## Über Straße\n", encoding="utf-8"
    )
    document = tmp_path / "doc.md"
    document.write_text(
        "# Doc\n\n## Own heading\n\n"
        "[a](other.md#kept-heading) [b](missing.md) [c](other.md#gone) [d](#own-heading) "
        "[e](#nowhere) [f](https://example.com/missing.md) [g](other.md#über-straße)\n",
        encoding="utf-8",
    )

    assert _broken_links(document) == ["missing.md", "other.md#gone", "#nowhere"]


def test_agents_md_lists_the_openspec_row_in_the_ci_suite() -> None:
    """The one place AGENTS.md names the rows of the gate ends with the row this step adds."""
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "actionlint, docs, deps, openspec)." in agents


# ── The release page and the changelog types the contributor guide names ────────────────────

_RELEASE_PLEASE_CONFIG = REPO_ROOT / "release-please-config.json"
_CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"
_RELEASE_CYCLE_MD = REPO_ROOT / "RELEASE_CYCLE.md"
_CHANGELOG_TABLE_HEADER = ["Title type", "Changelog section"]
# CommonMark with GitHub's tables, which the contributor guide uses for the changelog types.
_TABLE_MARKDOWN = MarkdownIt("commonmark").enable("table")


def _tables(document: Path) -> list[list[list[str]]]:
    """Each table of the Markdown document, as rows of the source text of each cell, the header
    row first."""
    tables: list[list[list[str]]] = []
    for token, following in pairwise(_TABLE_MARKDOWN.parse(document.read_text(encoding="utf-8"))):
        match token.type:
            case "table_open":
                tables.append([])
            case "tr_open":
                tables[-1].append([])
            case "th_open" | "td_open":
                tables[-1][-1].append(following.content)
    return tables


def _changelog_rows(document: Path) -> list[list[list[str]]]:
    """The body rows of each table in the document that lists title types and changelog
    sections."""
    return [rows for header, *rows in _tables(document) if header == _CHANGELOG_TABLE_HEADER]


def _visible_changelog_rows() -> list[list[str]]:
    """Each title type that release-please writes into the changelog, with its section, in the
    order of its configuration."""
    sections = json.loads(_RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"))["changelog-sections"]
    return [
        [f"`{section['type']}`", section["section"]]
        for section in sections
        if not section.get("hidden", False)
    ]


def test_contributing_md_names_the_changelog_types_release_please_shows() -> None:
    """The contributor guide says which title types add a changelog line. Its one table holds
    exactly the visible sections of `release-please-config.json`, in their order, so a change to
    the configuration changes the guide in the same pull request."""
    assert _changelog_rows(_CONTRIBUTING_MD) == [_visible_changelog_rows()]


def test_a_changelog_table_without_a_visible_type_does_not_match(tmp_path: Path) -> None:
    """Negative control: a guide whose table leaves out a visible type, or that has no table,
    does not match the configuration."""
    header = "| Title type | Changelog section |\n| :--- | :--- |\n"
    rows = "".join(f"| {kind} | {section} |\n" for kind, section in _visible_changelog_rows()[1:])
    short = tmp_path / "short.md"
    short.write_text(f"# Guide\n\n{header}{rows}", encoding="utf-8")
    bare = tmp_path / "bare.md"
    bare.write_text("# Guide\n\nNo table.\n", encoding="utf-8")

    assert (_changelog_rows(short), _changelog_rows(bare)) == (
        [_visible_changelog_rows()[1:]],
        [],
    )


def test_every_relative_link_of_the_release_page_resolves() -> None:
    """The release page a person follows links only files and headings that exist."""
    assert _broken_links(_RELEASE_CYCLE_MD) == []
