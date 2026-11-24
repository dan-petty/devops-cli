"""The context that a refine round gathers from the checkout for the model: the sections of a body,
the files and symbols an item cites, and the token budget (#1335).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.roadmap_stage import StageRepo
import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.body_hash import extract_section_and_outside, hash_text
from devops_cli.roadmap.refine.refine import (
    collect_context,
    inspect_checkout,
)
from devops_cli.roadmap.step_rules import GENERIC_RULES_HEADING, RULES_HEADING
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
    ctx = collect_context(git_repo, sha, body, max_tokens=4000)
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
    adr_file.write_text("# ADR 0016\nSpecial ADR content.\n", encoding="utf-8")
    new_sha = inspect_checkout(git_repo, REPO)

    ctx = collect_context(git_repo, new_sha, "body", max_tokens=4000)
    assert "Special ADR content." in ctx
    assert "0002-café decision with space.md" in ctx


def test_the_context_holds_the_agents_md_of_the_sha(stage_repo: StageRepo) -> None:
    """The context holds the `AGENTS.md` of the item's commit under its own heading, before the
    other sections of the repository (#4650)."""
    rule = "1. **A known first rule line.**"
    stage_repo.track({"AGENTS.md": f"# AGENTS.md\n\n{rule}\n"})
    sha = stage_repo.git("rev-parse", "HEAD")

    ctx = collect_context(stage_repo.clone, sha, "body", max_tokens=4000)

    heading = f"# {RULES_HEADING}"
    assert (heading in ctx, rule in ctx) == (True, True)
    assert ctx.index(heading) < ctx.index(rule)
    assert ctx.index(heading) < ctx.index("### CONTEXT.md")


def test_a_commit_without_context_md_keeps_the_rules_and_no_context_section(
    stage_repo: StageRepo,
) -> None:
    """`CONTEXT.md` stays optional: a commit with `AGENTS.md` and no `CONTEXT.md` gives the rules
    section and no `CONTEXT.md` section (#4650)."""
    stage_repo.track({"AGENTS.md": "# AGENTS.md\n\n1. **A known first rule line.**\n"})
    stage_repo.untrack("CONTEXT.md")
    sha = stage_repo.git("rev-parse", "HEAD")

    ctx = collect_context(stage_repo.clone, sha, "body", max_tokens=4000)

    assert (f"# {RULES_HEADING}" in ctx, "### CONTEXT.md" in ctx) == (True, False)


def test_the_context_takes_the_agents_md_of_the_sha_and_not_the_working_tree(
    stage_repo: StageRepo,
) -> None:
    """The context reads the `AGENTS.md` at the item's `sha`, not from the working tree (#4650)."""
    stage_repo.track({"AGENTS.md": "# AGENTS.md\n\n1. **Rule of the commit.**\n"})
    sha = stage_repo.git("rev-parse", "HEAD")
    (stage_repo.clone / "AGENTS.md").write_text(
        "# AGENTS.md\n\n1. **Rule of the working tree.**\n", encoding="utf-8"
    )

    ctx = collect_context(stage_repo.clone, sha, "body", max_tokens=4000)

    assert ("Rule of the commit." in ctx, "Rule of the working tree." in ctx) == (True, False)


def test_a_large_agents_md_section_stays_under_the_cap(stage_repo: StageRepo) -> None:
    """A 44,535-character `AGENTS.md` gives a section of at most
    `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens (#4650)."""
    line = "A rule of the target repository holds for every task. "
    text = (line * (44_535 // len(line) + 1))[:44_535]
    stage_repo.track({"AGENTS.md": f"# AGENTS.md\n\n{text}\n"})
    sha = stage_repo.git("rev-parse", "HEAD")

    ctx = collect_context(stage_repo.clone, sha, "body", max_tokens=200_000)

    section = ctx.split(f"# {RULES_HEADING}\n\n", 1)[1].split("\n\n### ", 1)[0]
    assert (len(text), count_tokens(section) <= CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS) == (
        44_535,
        True,
    )


def test_a_commit_without_agents_md_gets_the_generic_rules(stage_repo: StageRepo) -> None:
    """A commit with no `AGENTS.md` gets one section of the generic kit rules, under a heading that
    states that they are generic, and no rule of the working-tree file (#4650)."""
    (stage_repo.clone / "AGENTS.md").write_text(
        "# AGENTS.md\n\n1. **Rule of the working tree.**\n", encoding="utf-8"
    )
    sha = stage_repo.git("rev-parse", "HEAD")

    ctx = collect_context(stage_repo.clone, sha, "body", max_tokens=4000)

    headings = [
        line for line in ctx.splitlines() if line.startswith("# ") and "rules" in line.casefold()
    ]
    assert headings == [f"# {GENERIC_RULES_HEADING}"]
    assert "Rule of the working tree." not in ctx


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


def test_a_cited_rust_function_brings_its_definition_and_its_callers(
    stage_repo: StageRepo,
) -> None:
    """A symbol of another language than Python gets its section too: the files that name it, and
    the file and line of its definition, which tree-sitter confirms (#4638)."""
    stage_repo.track(
        {
            "src/game/unit.rs": "fn main() {\n    explorer_patrol_system();\n}\n\nfn explorer_patrol_system() {}\n",
            "tests/patrol.rs": "#[test]\nfn patrols() {\n    explorer_patrol_system();\n}\n",
        }
    )
    sha = stage_repo.git("rev-parse", "HEAD")

    ctx = collect_context(stage_repo.clone, sha, "Fix `explorer_patrol_system`.", max_tokens=4000)

    section = ctx.split("### Tests and callers of `explorer_patrol_system`")[1].split("###")[0]
    assert section.splitlines()[1:6] == [
        "Defined at: src/game/unit.rs:5",
        "Tests:",
        "- tests/patrol.rs",
        "Callers:",
        "- src/game/unit.rs",
    ]


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


def test_the_context_names_the_requirements_of_a_nested_capability(git_repo: Path) -> None:
    _write(git_repo, "src/devops_cli/widget/render.py", "def render_widget():\n    return 1\n")
    _write(
        git_repo,
        "openspec/specs/widget-render/output/spec.md",
        "### Requirement: A widget renders its output\nIt SHALL.\n",
    )
    _write(
        git_repo,
        "openspec/specs/named/by-path/spec.md",
        "### Requirement: The renderer is named by path\nSee `src/devops_cli/widget/render.py`.\n",
    )
    _write(
        git_repo,
        "openspec/specs/other/nested/spec.md",
        "### Requirement: An unrelated capability\nIt SHALL.\n",
    )
    sha = inspect_checkout(git_repo, REPO)

    ctx = collect_context(git_repo, sha, "Change src/devops_cli/widget/render.py now.", 4000)

    assert "### Requirements of widget-render/output\n- A widget renders its output" in ctx
    assert "### Requirements of named/by-path\n- The renderer is named by path" in ctx
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


def test_collect_identifiers_handles_git_grep_timeout(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow git grep that times out does not halt context collection (#4878)."""
    from devops_cli.roadmap.refine import refine

    sha = inspect_checkout(git_repo, REPO)
    body = "Review src/sample.py:1-2 and `slow_ident` identifier."

    original_run = refine.run_subprocess

    def mock_run_subprocess(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        if "grep" in cmd and "slow_ident" in cmd:
            raise subprocess.TimeoutExpired(cmd, 15)
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(refine, "run_subprocess", mock_run_subprocess)
    ctx = collect_context(git_repo, sha, body, max_tokens=4000)
    assert "Identifier matches" not in ctx
    assert "Project Context" in ctx


def test_collect_identifiers_bounds_and_excludes_archive_and_fixtures(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_collect_identifiers bounds git grep with --max-count=5 and excludes archive and fixtures (#4878)."""
    from devops_cli.roadmap.refine import refine

    sha = inspect_checkout(git_repo, REPO)
    body = "Review `some_ident` in code."

    recorded_cmds: list[list[str]] = []
    original_run = refine.run_subprocess

    def mock_run_subprocess(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        if "grep" in cmd:
            recorded_cmds.append(cmd)
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(refine, "run_subprocess", mock_run_subprocess)
    collect_context(git_repo, sha, body, max_tokens=1000)

    ident_grep = [cmd for cmd in recorded_cmds if "some_ident" in cmd and "--max-count=5" in cmd]
    assert len(ident_grep) == 1
    cmd = ident_grep[0]
    assert "-F" in cmd
    assert "-n" in cmd
    assert ":(exclude)openspec/changes/archive" in cmd
    assert ":(exclude)tests/fixtures" in cmd
