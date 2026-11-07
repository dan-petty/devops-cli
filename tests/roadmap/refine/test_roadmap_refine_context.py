"""The context that a refine round gathers from the checkout for the model: the sections of a body,
the files and symbols an item cites, and the token budget (#1335).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.body_hash import extract_section_and_outside, hash_text
from devops_cli.roadmap.refine.refine import (
    collect_context,
    inspect_checkout,
)
from tests.support.roadmap_refine import REPO

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_extract_section_and_outside_and_hashes() -> None:
    body_plain = "Heading\n\nSome body text without section."
    out1, sec1 = extract_section_and_outside(body_plain)
    assert (out1, sec1) == (body_plain, None)

    section_content = "\n## Proposed design\nProposal text.\n"
    body_with_sec = f"Intro\n{CONST_ROADMAP_REFINE_START_MARKER}{section_content}{CONST_ROADMAP_REFINE_END_MARKER}\nOutro"
    out2, sec2 = extract_section_and_outside(body_with_sec)
    assert (
        out2,
        sec2,
        hash_text("   hello   ") == hash_text("hello"),
    ) == (
        "Intro\n\nOutro",
        section_content,
        True,
    )


def test_inspect_checkout_origin_match_and_mismatch(git_repo: Path) -> None:
    sha = inspect_checkout(git_repo, REPO)
    assert len(sha) == 40

    with pytest.raises(GitHubOperationError, match="does not match"):
        inspect_checkout(git_repo, "other/mismatch-repo")


def test_collect_context_and_truncation(git_repo: Path) -> None:
    sha = inspect_checkout(git_repo, REPO)
    body = "Review src/sample.py:1-2 and `hello_world` identifier."
    ctx = collect_context(git_repo, sha, body, max_tokens=1000)
    assert (
        "Project Context" in ctx,
        "ADR 1" in ctx,
        "def hello_world" in ctx,
        "hello_world" in ctx,
    ) == (True, True, True, True)

    short_ctx = collect_context(git_repo, sha, body, max_tokens=10)
    assert "[truncated due to context budget]" in short_ctx


def test_collect_context_handles_spaces_and_non_ascii_adrs(git_repo: Path) -> None:
    """collect_context reads ADR files whose names have spaces or non-ASCII characters without C-quoting failure."""
    adr_file = git_repo / "docs" / "adr" / "0002-café decision with space.md"
    adr_file.write_text("# ADR 2\nSpecial ADR content.\n", encoding="utf-8")
    new_sha = inspect_checkout(git_repo, REPO)

    ctx = collect_context(git_repo, new_sha, "body", max_tokens=1000)
    assert "Special ADR content." in ctx
    assert "0002-café decision with space.md" in ctx


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_cited_symbol_brings_its_tests_and_its_callers(git_repo: Path) -> None:
    """The context lists the test files, then the caller files, that reference a cited symbol
    (#3012). A test file is under `tests/`, or is named `test_*.py` or `*_test.py`."""
    _write(git_repo, "tests/test_sample.py", "from src.sample import hello_world\n")
    _write(git_repo, "pkg/test_inline.py", "hello_world()\n")
    _write(git_repo, "pkg/inline_test.py", "hello_world()\n")
    _write(git_repo, "src/caller.py", "from sample import hello_world\n")
    _write(git_repo, "src/contest.py", "hello_world()\n")
    _write(git_repo, "src/unrelated.py", "nothing = 1\n")
    sha = inspect_checkout(git_repo, REPO)

    ctx = collect_context(git_repo, sha, "Call `hello_world` again.", max_tokens=4000)

    assert "### Tests and callers of `hello_world`" in ctx
    section = ctx.split("### Tests and callers of `hello_world`")[1]
    tests_part, callers_part = section.split("Callers:")
    assert (
        [
            f"- {p}" in tests_part
            for p in ("tests/test_sample.py", "pkg/test_inline.py", "pkg/inline_test.py")
        ],
        [f"- {p}" in callers_part for p in ("src/caller.py", "src/contest.py", "src/sample.py")],
        "src/unrelated.py" in section,
    ) == ([True, True, True], [True, True, True], False)


def test_a_symbol_with_no_other_file_adds_no_section(git_repo: Path) -> None:
    sha = inspect_checkout(git_repo, REPO)
    ctx = collect_context(git_repo, sha, "Call `missing_symbol` again.", max_tokens=4000)
    assert "Tests and callers" not in ctx


def test_the_paths_of_one_symbol_are_bounded_and_the_cut_is_noted(git_repo: Path) -> None:
    cap = constants.CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL
    for index in range(cap + 4):
        _write(git_repo, f"tests/test_n{index}.py", "hello_world()\n")
    sha = inspect_checkout(git_repo, REPO)

    ctx = collect_context(git_repo, sha, "Call `hello_world` again.", max_tokens=4000)

    section = ctx.split("### Tests and callers of `hello_world`")[1].split("###")[0]
    assert (section.count("\n- "), f"{cap} of {cap + 5} paths shown; 5 more" in section) == (
        cap,
        True,
    )


def test_a_cited_file_brings_the_requirement_names_of_its_capability(git_repo: Path) -> None:
    """A cited file belongs to the capabilities whose name is its package and module name, or
    that begin with that name, and to the specs that name its path (#3012)."""
    _write(git_repo, "src/devops_cli/widget/render.py", "def render_widget():\n    return 1\n")
    _write(
        git_repo,
        "openspec/specs/widget-render/spec.md",
        "# widget-render\n\n## Requirements\n\n### Requirement: A widget renders\nIt SHALL.\n\n"
        "#### Scenario: One\n\n### Requirement: A widget has a title\nIt SHALL.\n",
    )
    _write(
        git_repo,
        "openspec/specs/widget/spec.md",
        "### Requirement: The widget package is documented\nIt SHALL.\n",
    )
    _write(
        git_repo,
        "openspec/specs/named-by-path/spec.md",
        "### Requirement: The renderer is named by path\nSee `src/devops_cli/widget/render.py`.\n",
    )
    _write(
        git_repo,
        "openspec/specs/other/spec.md",
        "### Requirement: An unrelated capability\nIt SHALL.\n",
    )
    sha = inspect_checkout(git_repo, REPO)

    ctx = collect_context(git_repo, sha, "Change src/devops_cli/widget/render.py now.", 4000)

    assert "### Requirements of widget-render" in ctx
    assert "- A widget renders\n- A widget has a title" in ctx
    assert "### Requirements of named-by-path\n- The renderer is named by path" in ctx
    # The budget cuts the end first, so the short sections come before the cited code.
    assert ctx.index("### Requirements of widget-render") < ctx.index("### Code: src/devops_cli")
    assert "- The widget package is documented" in ctx
    assert "An unrelated capability" not in ctx


def test_a_cited_file_with_no_capability_adds_no_requirement_section(git_repo: Path) -> None:
    _write(git_repo, "openspec/specs/other/spec.md", "### Requirement: Unrelated\nIt SHALL.\n")
    sha = inspect_checkout(git_repo, REPO)
    ctx = collect_context(git_repo, sha, "Review src/sample.py:1-2 now.", max_tokens=4000)
    assert "### Requirements of" not in ctx


def test_the_larger_context_stays_inside_the_token_budget(git_repo: Path) -> None:
    for index in range(40):
        _write(git_repo, f"tests/test_budget_{index}.py", "hello_world()\n")
    sha = inspect_checkout(git_repo, REPO)
    body = "Review src/sample.py:1-2 and `hello_world` identifier."

    ctx = collect_context(git_repo, sha, body, max_tokens=120)

    assert count_tokens(ctx) <= 120
