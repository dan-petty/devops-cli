"""Offline test suite asserting claims made in AGENTS.md and related documentation."""

from __future__ import annotations

import re
from collections import deque
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import Final
from urllib.parse import unquote, urlsplit

import pytest
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.anchors import anchors_plugin

from devops_cli.ai.instruction_generator import (
    POINTER_STUBS,
    generate_instruction_content,
    parse_project_metadata,
    scaffold_agent_instructions,
)
from devops_cli.config.constants import (
    CONST_AGENTS_MD_MAX_CHARS,
    CONST_AGENTS_MD_ROUTES,
    CONST_DOCS_CLASS_GENERATED,
    CONST_DOCS_CLASS_HAND_WRITTEN,
)
from devops_cli.docs.inventory import documents_of_class
from tests.support.markdown_tables import routing_rows, tables, where_to_look
from tests.support.paths import REPO_ROOT

CONST_DELETED_PROCESS_TERMS: Final[tuple[str, ...]] = (
    "release branch",
    "`release/",
    "release/*",
    "release/v",
    "the cut",
    "cut PR",
    "changelog fragment",
    "changelog.d",
    "towncrier",
    "Part of #",
    "roadmap reprioritize",
    "roadmap close",
    "roadmap render",
    "roadmap migrate",
    "docs/ROADMAP.md",
    "devops release",
    "filing quota",
    "budget/borrowed",
    "#1153",
    # #1916 retired the review guards file. Suppressions and severity caps sit in
    # `.devops/review.toml`.
    ".devops/review.md",
    # A branch is `<type>/<issue>-<slug>`, stated once in CONTRIBUTING.md (#2292).
    "topic branch prefixes",
    "feat/<",
    "fix/<",
    "docs/<",
    "refactor/<",
    "<type>/<name>",
    "feature/<name>",
    # The pre-push hook runs only the fast static checks (#1752).
    "pre-push gate",
    "pre-push `uv run devops ci`",
    "pre-push hook runs `uv run devops ci`",
    "pre-push hook runs the full gate",
    "pre-push hook runs the same gate",
)


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
    assert "security_advisory.yml" not in templates, (
        "Deprecated templates must not be referenced in AGENTS.md"
    )
    assert "task.yml" not in templates, "Deprecated templates must not be referenced in AGENTS.md"


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


def _scaffold_with_every_routed_document(root: Path) -> Path:
    """A project that holds every document a generated AGENTS.md can route to, scaffolded."""
    for path, _task in CONST_AGENTS_MD_ROUTES:
        target = root / path
        if path.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Document\n", encoding="utf-8")
    scaffold_agent_instructions(root)
    return root / "AGENTS.md"


def test_agents_md_stays_within_character_budget(tmp_path: Path) -> None:
    """AGENTS.md is a router that every agent reads in full, so it, and the AGENTS.md that
    `devops ai agents` writes with every routed document, fit a cap of at most 4,500 characters
    (#1961, #5421)."""
    generated = _scaffold_with_every_routed_document(tmp_path).read_text(encoding="utf-8")
    assert (
        CONST_AGENTS_MD_MAX_CHARS <= 4_500,
        len((REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")) <= CONST_AGENTS_MD_MAX_CHARS,
        len(generated) <= CONST_AGENTS_MD_MAX_CHARS,
    ) == (True, True, True)


def test_agents_md_routes_each_kind_of_task_to_a_document_that_exists() -> None:
    """Each row of the routing table of AGENTS.md links a document, and each document it links
    exists, so a moved document fails here rather than in an agent's session (#1961)."""
    rows = routing_rows(_AGENTS_MD)
    links = where_to_look(_AGENTS_MD)
    assert (
        len(rows) >= 10,
        [task for task, hrefs in links.items() if not hrefs],
        [
            href
            for hrefs in links.values()
            for href in hrefs
            if not (_AGENTS_MD.parent / unquote(urlsplit(href).path)).exists()
        ],
    ) == (True, [], [])


def test_a_generated_agents_md_routes_only_to_documents_that_exist(tmp_path: Path) -> None:
    """`devops ai agents` writes a table row only for a routed document that exists in the
    target, and every link of the document resolves, with all routed documents present and with
    none (#1961)."""
    full = _scaffold_with_every_routed_document(tmp_path / "full")
    bare_root = tmp_path / "bare"
    bare_root.mkdir()
    scaffold_agent_instructions(bare_root)
    bare = bare_root / "AGENTS.md"

    assert (
        _broken_links(full),
        len(routing_rows(full)),
        _broken_links(bare),
        [task for task, _read in routing_rows(bare)],
    ) == ([], len(CONST_AGENTS_MD_ROUTES) + 1, [], ["learn a `devops` command"])


def test_a_generated_agents_md_routes_no_task_to_a_review_guards_file(tmp_path: Path) -> None:
    """`devops ai agents` names no `.devops/review.md`, also in a project that keeps one, because
    no review stage reads such a file (#1916)."""
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.md").write_text("# Review guards\n", encoding="utf-8")
    scaffold_agent_instructions(tmp_path)

    assert ".devops/review.md" not in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


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


def _documents_within(start: Path, links: int) -> set[Path]:
    """`start` and each Markdown file that a chain of at most `links` links from it reaches."""
    reached = {start.resolve(): 0}
    queue = deque(reached)
    while queue:
        document = queue.popleft()
        if reached[document] == links:
            continue
        for target, _fragment in _relative_links(document).values():
            if target.suffix == ".md" and target.is_file() and target not in reached:
                reached[target] = reached[document] + 1
                queue.append(target)
    return set(reached)


def test_every_hand_written_and_generated_document_is_within_two_links_of_agents_md() -> None:
    """An agent reads AGENTS.md, and a document that no chain of two links from it reaches is a
    document that the router does not route to: the settings, error, metric and command
    references, the OpenTofu guide and the pages of each command group were such documents
    (#2293). Decision records, prompts and the tools' own files are out of scope."""
    reached = _documents_within(_AGENTS_MD, 2)
    documents = sorted(
        path.resolve()
        for kind in (CONST_DOCS_CLASS_HAND_WRITTEN, CONST_DOCS_CLASS_GENERATED)
        for path in documents_of_class(REPO_ROOT, kind)
    )

    assert (
        len(documents) > 100,
        [str(path.relative_to(REPO_ROOT)) for path in documents if path not in reached],
    ) == (True, [])


def test_a_document_three_links_from_the_start_is_not_within_two(tmp_path: Path) -> None:
    """Negative control: the walk counts links, and stops at the limit."""
    names = ["start", "one", "two", "three"]
    for name, following in pairwise(names):
        (tmp_path / f"{name}.md").write_text(f"[next]({following}.md)\n", encoding="utf-8")
    (tmp_path / "three.md").write_text("The end.\n", encoding="utf-8")

    assert _documents_within(tmp_path / "start.md", 2) == {
        (tmp_path / f"{name}.md").resolve() for name in names[:3]
    }


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


# ── No agent instruction names a deleted process (#1961) ─────────────────────────────────────

_AGENTS_MD = REPO_ROOT / "AGENTS.md"


# ── The test files that the test rules name exist (#3508) ────────────────────────────────────


def _marked_target(following: list[Token]) -> bool:
    """Whether an emphasis that starts with `(target` follows, with only spaces between."""
    rest = [t for t in following if not (t.type in {"text", "softbreak"} and not t.content.strip())]
    return len(rest) > 1 and rest[0].type == "em_open" and rest[1].content.startswith("(target")


def _missing_test_paths(document: Path, root: Path) -> list[str]:
    """Each backticked `tests/` path of the document that is absent under `root`.

    A path with a `<placeholder>` is checked up to the placeholder. A path that an
    `*(target ...)*` mark follows names a file that is planned, so it needs no file.
    """
    missing: list[str] = []
    for block in _MARKDOWN.parse(document.read_text(encoding="utf-8")):
        children = block.children or []
        for index, token in enumerate(children):
            if token.type != "code_inline" or not re.fullmatch(r"tests/\S*", token.content):
                continue
            if _marked_target(children[index + 1 :]):
                continue
            if not (root / token.content.split("<")[0]).exists():
                missing.append(token.content)
    return missing


def test_the_test_rules_name_only_test_files_that_exist() -> None:
    """A test path in docs/TESTING.md that is gone or moved sends an agent to the wrong place.
    Each backticked `tests/` path of the test rules exists, or is a placeholder or a target."""
    assert _missing_test_paths(_TESTING_MD, REPO_ROOT) == []


def test_a_test_path_that_is_gone_is_reported(tmp_path: Path) -> None:
    """Negative control: a path to a file that is not there is named, and a directory or a file
    that is there passes."""
    (tmp_path / "tests" / "ai").mkdir(parents=True)
    (tmp_path / "tests" / "ai" / "test_here.py").write_text("", encoding="utf-8")
    document = tmp_path / "TESTING.md"
    document.write_text(
        "See `tests/ai/test_here.py`, `tests/ai/` and `tests/test_gone.py`.\n", encoding="utf-8"
    )

    assert _missing_test_paths(document, tmp_path) == ["tests/test_gone.py"]


def test_a_placeholder_and_a_target_test_path_pass(tmp_path: Path) -> None:
    """A planned fake (`<edge>`) and a planned test marked `*(target)*` need no file, but a
    placeholder under a directory that is not there, or a path with another mark, is named."""
    (tmp_path / "tests" / "support" / "fakes").mkdir(parents=True)
    document = tmp_path / "TESTING.md"
    document.write_text(
        "Fakes sit in `tests/support/fakes/<edge>.py`. A planned test is\n"
        "`tests/roadmap/test_duplicate_candidates.py` *(target)* and\n"
        "`tests/commands/` *(target: a few do today)*.\n"
        "Not planned: `tests/nowhere/<edge>.py` and `tests/old/test_a.py` *(see below)*.\n",
        encoding="utf-8",
    )

    assert _missing_test_paths(document, tmp_path) == [
        "tests/nowhere/<edge>.py",
        "tests/old/test_a.py",
    ]


# ── The release page and the naming rules of the contributor guide ──────────────────────────

_RELEASE_CYCLE_MD = REPO_ROOT / "RELEASE_CYCLE.md"


def test_every_relative_link_of_the_release_page_resolves() -> None:
    """The release page a person follows links only files and headings that exist."""
    assert _broken_links(_RELEASE_CYCLE_MD) == []


_CONTROL_TABLE_HEADER: Final[list[str]] = [
    "Control",
    "Scope",
    "Compensating control",
    "Evidence",
    "Approved by",
    "Reviewed",
]
_REVIEW_DATE_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}")


def _dedicated_resources_section() -> str:
    """Text of `SECURITY.md` between the Dedicated Resources heading and the next `## ` heading."""
    text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    match = re.search(
        r"^## Dedicated Development Resources and Sandboxes\n(.*?)(?=\n## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    assert match is not None, "SECURITY.md lacks Dedicated Development Resources and Sandboxes"
    return match.group(1)


def _control_table_errors(document: Path) -> list[str]:
    """Return validation failures for the security control table in `document`."""
    matching = [rows for header, *rows in tables(document) if header == _CONTROL_TABLE_HEADER]
    if len(matching) != 1:
        return ["missing control table with header " + " | ".join(_CONTROL_TABLE_HEADER)]
    errors: list[str] = []
    for index, row in enumerate(matching[0], start=1):
        label = row[0].strip() if row else ""
        row_name = f"row {index}" + (f" ({label})" if label else "")
        for column, cell in zip(_CONTROL_TABLE_HEADER, row, strict=False):
            if not cell.strip():
                errors.append(f"{row_name}: empty {column}")
        if len(row) != len(_CONTROL_TABLE_HEADER):
            errors.append(
                f"{row_name}: expected {len(_CONTROL_TABLE_HEADER)} cells, got {len(row)}"
            )
            continue
        reviewed = row[-1].strip()
        if reviewed:
            try:
                if not _REVIEW_DATE_RE.fullmatch(reviewed):
                    raise ValueError
                date.fromisoformat(reviewed)
            except ValueError:
                errors.append(f"{row_name}: invalid Reviewed date {reviewed!r}")
    return errors


def test_security_md_states_dedicated_resources_and_sandbox_controls_policy() -> None:
    """`SECURITY.md` states the policy for dedicated development resources and sandboxes, lists
    the resources by role, and holds a valid control table (#5447)."""
    section = _dedicated_resources_section()
    for token in (
        "**Default.**",
        "**Conditions.**",
        "**Never changed.**",
        "**Approval.**",
        "owner",
        "homelab",
        "devcontainer",
        "project-owned test namespaces and repositories",
        "RuntimeClass `gvisor`",
        "review sandbox",
        "planner run Job",
    ):
        assert token in section, f"Missing required policy token {token!r}"
    assert _control_table_errors(REPO_ROOT / "SECURITY.md") == []


def test_control_table_accepts_empty_header_only_table(tmp_path: Path) -> None:
    """A control table with only the header row and no exception entries is valid."""
    doc = tmp_path / "SECURITY.md"
    doc.write_text(
        "| " + " | ".join(_CONTROL_TABLE_HEADER) + " |\n| --- | --- | --- | --- | --- | --- |\n",
        encoding="utf-8",
    )
    assert _control_table_errors(doc) == []


@pytest.mark.parametrize("missing_column", _CONTROL_TABLE_HEADER)
def test_control_table_rejects_empty_cell_and_names_row_and_column(
    tmp_path: Path, missing_column: str
) -> None:
    """Every data row in the control table must fill all six columns."""
    values = [
        "Allow git in sandbox",
        "RuntimeClass gvisor",
        "gVisor boundary",
        "37 refusals",
        "The owner",
        "2026-11-25",
    ]
    values[_CONTROL_TABLE_HEADER.index(missing_column)] = ""
    doc = tmp_path / "SECURITY.md"
    doc.write_text(
        "| " + " | ".join(_CONTROL_TABLE_HEADER) + " |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| " + " | ".join(values) + " |\n",
        encoding="utf-8",
    )
    errors = _control_table_errors(doc)
    assert any("row 1" in error and missing_column in error for error in errors), errors


@pytest.mark.parametrize("bad_date", ["next month", "2026-13-01", "2026/11/25"])
def test_control_table_rejects_non_iso_review_date(tmp_path: Path, bad_date: str) -> None:
    """The `Reviewed` column must hold an ISO 8601 `YYYY-MM-DD` calendar date."""
    doc = tmp_path / "SECURITY.md"
    doc.write_text(
        "| " + " | ".join(_CONTROL_TABLE_HEADER) + " |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"| Control | Scope | Boundary | Counts | The owner | {bad_date} |\n",
        encoding="utf-8",
    )
    errors = _control_table_errors(doc)
    assert any("row 1" in error and bad_date in error for error in errors), errors
