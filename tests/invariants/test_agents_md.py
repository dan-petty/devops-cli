"""Offline test suite asserting claims made in AGENTS.md and related documentation."""

from __future__ import annotations

import json
import re
import tomllib
from collections import deque
from itertools import pairwise, takewhile
from pathlib import Path
from typing import Final
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.anchors import anchors_plugin

from devops_cli.ai.instruction_generator import (
    POINTER_STUBS,
    generate_agents_md,
    generate_instruction_content,
    parse_project_metadata,
    scaffold_agent_instructions,
)
from devops_cli.ai.personas import Persona
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


# The rules of AGENTS.md that only devops-cli has, so the template of `devops ai agents` does
# not hold them: its writing standard (owner decision D2 of #1961).
CONST_DEVOPS_CLI_ONLY_RULES: Final[frozenset[str]] = frozenset({"Write prose in ASD-STE100"})


def _bold_start(inline: Token) -> str | None:
    """The bold text that starts an inline token, less its end mark, or None."""
    children = [child for child in inline.children or [] if child.content or child.markup]
    if not children or children[0].type != "strong_open":
        return None
    bold = takewhile(lambda child: child.type != "strong_close", children[1:])
    return "".join(
        f"`{child.content}`" if child.type == "code_inline" else child.content for child in bold
    ).rstrip(".:")


def _rule_titles(markdown: str) -> list[str]:
    """The bold title of each numbered rule under `## Rules for every task`."""
    tokens = MarkdownIt().parse(markdown)
    start = next(i for i, token in enumerate(tokens) if token.content == "Rules for every task")
    end = next(i for i in range(start, len(tokens)) if tokens[i].type == "ordered_list_close")
    titles = (_bold_start(token) for token in tokens[start + 1 : end] if token.type == "inline")
    return [title for title in titles if title is not None]


def _rule_drift(agents_md: str, generated: str) -> tuple[list[str], list[str]]:
    """The rule titles of `agents_md` that neither `generated` nor the devops-cli list holds, and
    the rule titles of `generated` that `agents_md` does not hold."""
    ours, template = _rule_titles(agents_md), _rule_titles(generated)
    return (
        [title for title in ours if title not in template + list(CONST_DEVOPS_CLI_ONLY_RULES)],
        [title for title in template if title not in ours],
    )


def test_the_template_holds_each_rule_of_agents_md_that_is_not_only_for_devops_cli() -> None:
    """The template of `devops ai agents`, rendered for devops-cli, has the rule titles of
    AGENTS.md, less the rules that only devops-cli has, so a new rule reaches the template or
    the list on purpose (#4641). The test compares titles, not bytes: AGENTS.md is near its cap."""
    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    generated = generate_agents_md(parse_project_metadata(REPO_ROOT))
    assert (
        _rule_drift(agents_md, generated),
        len(_rule_titles(generated)) >= 10,
    ) == (([], []), True)


def test_a_rule_title_added_only_to_agents_md_is_reported() -> None:
    """A rule title that AGENTS.md adds, and that is not in the template or in the devops-cli
    list, is reported; a title of the devops-cli list is not (#4641)."""
    agents_md = (
        "## Rules for every task\n\n"
        "1. **Fix the cause.** Text.\n"
        "2. **Pin every tool.** Text.\n"
        "3. **Write prose in ASD-STE100** for text.\n"
    )
    generated = "## Rules for every task\n\n1. **Fix the cause.** Text.\n2. **Back up.** Text.\n"
    assert _rule_drift(agents_md, generated) == (["Pin every tool"], ["Back up"])


def test_the_sdlc_closes_an_item_that_a_newer_direction_replaces() -> None:
    """The triage rules of docs/SDLC.md, not AGENTS.md, tell an agent to close an item that a
    newer direction replaces as not planned (#5421)."""
    content = (REPO_ROOT / "docs" / "SDLC.md").read_text(encoding="utf-8")
    assert "Close an item that a newer direction replaces as not planned" in content


def test_agents_md_asks_for_small_tool_output_and_keeps_the_facts_the_reader_needs() -> None:
    """Tool results are most of the tokens that an agent carries, so one rule asks each command
    for less output, and it names the facts that a shorter output keeps (#4471)."""
    content = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    rules = [line for line in content.splitlines() if "**Keep tool output small.**" in line]
    assert [
        needle
        for needle in (
            "Search before you read",
            "`git diff --stat`",
            "`--jq`",
            "`--limit`",
            "Loki `limit`",
            "error lines",
            "`file:line`",
            "failed test IDs",
        )
        if needle not in "".join(rules)
    ] == []


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


def test_agents_md_routes_a_closed_model_question_to_the_ask_jev_skill() -> None:
    """The decision model rule left the rules of AGENTS.md: a row routes a closed question for a
    model to the `ask-jev` skill, and the skill tells an agent to ask only when no file or
    deterministic check can answer (#5421)."""
    skill = (REPO_ROOT / ".agents" / "skills" / "ask-jev" / "SKILL.md").read_text(encoding="utf-8")
    assert (
        where_to_look(_AGENTS_MD).get("ask a model a closed question"),
        "no file or deterministic check can answer" in skill,
    ) == ([".agents/skills/ask-jev/SKILL.md"], True)


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


def test_the_gate_list_of_the_sdlc_names_the_openspec_row() -> None:
    """docs/SDLC.md, the document AGENTS.md routes the gate to, lists the `openspec` row as the
    last check that `devops ci` runs."""
    sdlc = (REPO_ROOT / "docs" / "SDLC.md").read_text(encoding="utf-8")
    assert "14. `openspec`: Runs `devops openspec check`" in sdlc


# ── No agent instruction names a deleted process (#1961) ─────────────────────────────────────

_AGENTS_MD = REPO_ROOT / "AGENTS.md"
# The files that instruct an agent: AGENTS.md and its pointer stubs, the documents it routes
# work to, the model prompts, the personas and the knowledge base. Decision records, the glossary
# and the records of past review sessions are not instructions, so they are out of scope.
_AGENT_INSTRUCTION_GLOBS = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/*.yml",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "RELEASE_CYCLE.md",
    "SECURITY.md",
    "docs/CLUSTER.md",
    "docs/ROUTINE_TASKS.md",
    "docs/SDLC.md",
    "docs/TESTING.md",
    "docs/agent/README.md",
    "k8s/README.md",
    "openspec/config.yaml",
    "src/devops_cli/ai/knowledge_base/**/*.md",
    "src/devops_cli/ai/personas/**/*.md",
    "src/devops_cli/ai/tasks/**/*.md",
)


def _deleted_process_names(texts: dict[str, str]) -> dict[str, list[str]]:
    """Each text that names a deleted process, with the names it holds."""
    return {
        name: found
        for name, text in texts.items()
        if (found := [term for term in CONST_DELETED_PROCESS_TERMS if term in text])
    }


def test_no_agent_instruction_names_a_deleted_process(tmp_path: Path) -> None:
    """An instruction that names a release branch, the cut, a changelog fragment, the planner,
    the filing quota or the full gate in the pre-push hook sends an agent into a process that no
    longer exists. No agent instruction, and no AGENTS.md that `devops ai agents` writes, names
    one."""
    paths = sorted({path for glob in _AGENT_INSTRUCTION_GLOBS for path in REPO_ROOT.glob(glob)})
    texts = {str(path.relative_to(REPO_ROOT)): path.read_text(encoding="utf-8") for path in paths}
    generated = _scaffold_with_every_routed_document(tmp_path)
    texts["generated AGENTS.md"] = generated.read_text(encoding="utf-8")

    assert (len(paths) > 100, _deleted_process_names(texts)) == (True, {})


def test_a_text_that_names_a_deleted_process_is_reported() -> None:
    """Negative control: the check names each deleted process a text holds, and passes a text
    that names only the processes in use."""
    texts = {
        "old.md": "Open the pull request against the release branch, then run the cut.",
        "new.md": "Open the pull request into `main`. release-please makes the release.",
    }
    assert _deleted_process_names(texts) == {"old.md": ["release branch", "the cut"]}


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


# ── The release page and the changelog types the contributor guide names ────────────────────

_RELEASE_PLEASE_CONFIG = REPO_ROOT / "release-please-config.json"
_CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"
_RELEASE_CYCLE_MD = REPO_ROOT / "RELEASE_CYCLE.md"
_CHANGELOG_TABLE_HEADER = ["Title type", "Changelog section"]


def _changelog_rows(document: Path) -> list[list[list[str]]]:
    """The body rows of each table in the document that lists title types and changelog
    sections."""
    return [rows for header, *rows in tables(document) if header == _CHANGELOG_TABLE_HEADER]


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


_NAMING_TABLE_HEADER = ["Artifact", "Form", "Check"]


def _naming_section(document: Path) -> str:
    """The text of the "Naming" section of the contributor guide, up to the next section."""
    text = document.read_text(encoding="utf-8")
    start = text.index("\n## 5. Naming\n")
    return text[start : text.find("\n## ", start + 1)]


def test_contributing_md_states_the_branch_form_once_and_names_each_check() -> None:
    """The one table of naming rules gives every artifact its form and the check that enforces
    it, or says that none does. The branch row holds the form, and the text after the table names
    each type that release-please reads, so a branch type and a title type are the same list
    (#2292)."""
    [rows] = [rows for header, *rows in tables(_CONTRIBUTING_MD) if header == _NAMING_TABLE_HEADER]
    forms = {artifact: form for artifact, form, _check in rows}
    sections = json.loads(_RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"))["changelog-sections"]
    section = _naming_section(_CONTRIBUTING_MD)

    assert (
        forms["Branch"],
        [artifact for artifact, _form, check in rows if not check.strip()],
        [f"`{item['type']}`" for item in sections if f"`{item['type']}`" not in section],
        section.count("`<type>/<issue>-<slug>`"),
    ) == ("`<type>/<issue>-<slug>`", [], [], 1)


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


_PYPROJECT = REPO_ROOT / "pyproject.toml"
_COVERAGE_FLOOR_STATEMENT = re.compile(
    r"(?:Minimum|floor is) (\d+)% (?:Code Coverage|of the lines)"
)


def _coverage_floors_stated(document: Path) -> list[int]:
    """The coverage floors that a document states, in the order it states them."""
    text = document.read_text(encoding="utf-8")
    return [int(figure) for figure in _COVERAGE_FLOOR_STATEMENT.findall(text)]


def test_the_coverage_run_table_measures_branches() -> None:
    """`[tool.coverage.run]` measures both sides of each conditional in every row of the gate,
    and it keeps the data file that the aggregate job combines (#2163)."""
    run = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["tool"]["coverage"]["run"]

    assert run == {"data_file": ".data/.coverage", "parallel": True, "branch": True}


def test_the_contributor_guide_and_the_test_rules_state_the_coverage_floor_of_pyproject() -> None:
    """Two documents give the figure of the coverage floor, once each, and it is the
    `fail_under` of `pyproject.toml`. Every other document names the gate without a figure, so a
    change of the floor changes two sentences (#2356)."""
    floor = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["tool"]["coverage"]["report"][
        "fail_under"
    ]

    assert (_coverage_floors_stated(_CONTRIBUTING_MD), _coverage_floors_stated(_TESTING_MD)) == (
        [floor],
        [floor],
    )


def test_a_document_that_states_another_coverage_floor_is_reported(tmp_path: Path) -> None:
    """Negative control: a guide with the old figure, or with no statement, is not the floor."""
    old = tmp_path / "old.md"
    old.write_text("- **Minimum 90% Code Coverage**: gate.\n", encoding="utf-8")
    none = tmp_path / "none.md"
    none.write_text("- The gate has a floor.\n", encoding="utf-8")

    assert (_coverage_floors_stated(old), _coverage_floors_stated(none)) == ([90], [])


CONST_RETIRED_TEST_PHRASES: Final[tuple[str, ...]] = (
    "tuple equality",
    "using mocks (`unittest.mock`, `pytest-mock`)",
    "tests/test_<submodule>.py",
    "BaseLLMProvider",
    "__test__ = False",
)


def _find_retired_test_phrases(content: str) -> list[tuple[int, str]]:
    """Lines and retired phrases found in text, ignoring case."""
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        line_lower = line.lower()
        for phrase in CONST_RETIRED_TEST_PHRASES:
            if phrase.lower() in line_lower:
                found.append((lineno, phrase))
    return found


def test_agents_md_holds_no_retired_test_rules() -> None:
    """AGENTS.md holds no retired test rule phrases (#1336)."""
    agents_path = REPO_ROOT / "AGENTS.md"
    content = agents_path.read_text(encoding="utf-8")
    violations = _find_retired_test_phrases(content)
    assert violations == [], f"Found retired test phrases: {violations}"


def test_retired_test_phrase_in_agents_md_fails_ban(tmp_path: Path) -> None:
    """A file holding a retired phrase fails the ban, naming the line and phrase (#1336)."""
    doc = tmp_path / "AGENTS.md"
    doc.write_text("Rule: assert tuple equality in all tests.\n", encoding="utf-8")
    assert _find_retired_test_phrases(doc.read_text(encoding="utf-8")) == [(1, "tuple equality")]


def _trivy_config_rule() -> str:
    """The text of the section of SECURITY.md that judges a `Trivy-config` alert (#4401)."""
    text = Path("SECURITY.md").read_text(encoding="utf-8")
    start = text.index("## Judging a Trivy-config Alert")
    end = text.find("\n## ", start + 1)
    return " ".join(text[start : end if end != -1 else None].split())


def test_the_policy_names_the_judge_the_time_and_the_ignore_file() -> None:
    rule = _trivy_config_rule()

    assert "owner" in rule
    assert "CRITICAL" in rule
    assert "24 hours" in rule
    assert "agent" in rule
    assert "14 days" in rule
    assert "`.trivyignore.yaml`" in rule
    assert "`statement`" in rule
    assert "`expired_at`" in rule


def test_the_policy_keeps_the_limits_of_a_finding_with_no_fix() -> None:
    rule = _trivy_config_rule()

    assert "A Finding with No Fix" in rule
    assert "3 days" in rule
