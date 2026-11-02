"""Tests for the read-only toolbox of the stage planner (#3037): nine tools on the staged commit
of a temporary git repository with two commits. No test reaches a model or the network."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_INVESTIGATION_MAX_BLOB_BYTES,
    CONST_ROADMAP_REFINE_TOOL_MAX_CHARS,
    CONST_ROADMAP_REFINE_TOOL_MAX_LINES,
    CONST_ROADMAP_STAGE_MAP_LINE_CHARS,
    CONST_ROADMAP_STAGE_MAP_MAX_FILES,
)
from devops_cli.openspec.tool import OpenSpecTool, isolated_openspec
from devops_cli.roadmap.stage_tools import StageTools

_TOOL_NAMES = [
    "list_files",
    "read_file",
    "search_code",
    "git_log",
    "git_show",
    "file_symbols",
    "callers",
    "repo_map",
    "read_spec",
]
if TYPE_CHECKING:
    from tests.support.fakes.openspec import OpenSpecFake

_SPEC = """# Sample

## Purpose
The sample spec greets people and leaves politely, for the tests.

## Requirements

### Requirement: The sample greets
The sample SHALL greet.

#### Scenario: A greeting
- **WHEN** it runs
- **THEN** it greets

### Requirement: The sample leaves
The sample SHALL leave.
"""


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _commit(repo: Path, message: str, files: dict[str, str]) -> str:
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A checkout with two commits. The first adds `src/sample.py` and the spec; the second adds
    `src/caller.py` and changes `src/sample.py`."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(root, "config", key, value)
    _git(root, "config", "commit.gpgsign", "false")
    _commit(
        root,
        "first",
        {
            "src/sample.py": "def hello_world():\n    return 'hello'\n",
            "openspec/specs/sample/spec.md": _SPEC,
        },
    )
    _commit(
        root,
        "second",
        {
            "src/sample.py": "def hello_world():\n    return 'hi'\n\n\nclass Greeter:\n    pass\n",
            "src/caller.py": "from sample import hello_world\n\nvalue = hello_world()\n",
        },
    )
    return root


# What `openspec list --specs --json` and `openspec show sample --type spec --json` print for `_SPEC`
# (OpenSpec 1.14.3, trimmed of the fields the tool does not read).
_LIST = json.dumps({"specs": [{"id": "sample", "requirementCount": 2}]})
_SHOW = json.dumps(
    {
        "id": "sample",
        "requirements": [
            {
                "name": "The sample greets",
                "text": "The sample SHALL greet.",
                "scenarios": [
                    {
                        "name": "A greeting",
                        "rawText": "- **WHEN** it runs\n- **THEN** it greets",
                    }
                ],
            },
            {"name": "The sample leaves", "text": "The sample SHALL leave.", "scenarios": []},
        ],
    }
)


@pytest.fixture
def tools(repo: Path, openspec_fake: OpenSpecFake, tmp_path: Path) -> StageTools:
    openspec_fake.script(("list", "--specs", "--json"), 0, _LIST)
    openspec_fake.script(("show", "sample", "--type", "spec", "--json"), 0, _SHOW)
    return StageTools(
        source=repo, sha=_git(repo, "rev-parse", "HEAD"), openspec=OpenSpecTool(tmp_path / "cfg")
    )


def test_the_toolbox_has_nine_read_only_tools_and_no_web_search(tools: StageTools) -> None:
    assert [tool.name for tool in tools.tools()] == _TOOL_NAMES


def test_the_toolbox_has_no_web_search_even_with_a_key(repo: Path) -> None:
    keyed = StageTools(source=repo, sha="HEAD", firecrawl_key="fc-key")

    assert "search_web" not in [tool.name for tool in keyed.tools()]


def test_the_inherited_tools_read_the_commit(tools: StageTools) -> None:
    assert (
        tools.list_files("src").splitlines(),
        tools.read_file("src/caller.py", 3, 3),
        tools.search_code("hello_world").splitlines()[0],
    ) == (
        ["src/caller.py", "src/sample.py"],
        "3: value = hello_world()",
        "src/caller.py:1:from sample import hello_world",
    )


def test_git_log_lists_the_commits_that_changed_a_path(tools: StageTools) -> None:
    assert (
        [line.split(" ", 2)[2] for line in tools.git_log("src/caller.py").splitlines()],
        [line.split(" ", 2)[2] for line in tools.git_log("src/sample.py").splitlines()],
        [line.split(" ", 2)[2] for line in tools.git_log().splitlines()],
    ) == (["second"], ["second", "first"], ["second", "first"])


def test_git_log_answers_a_path_outside_the_repository_as_text(tools: StageTools) -> None:
    assert tools.git_log("../outside") == "The path ../outside is outside the repository."


def test_git_show_shows_a_commit(tools: StageTools, repo: Path) -> None:
    first = _git(repo, "rev-parse", "HEAD~1")

    shown = tools.git_show(first[:10])
    limited = tools.git_show(first, "src/sample.py")

    assert ("+def hello_world():" in shown, "first" in shown, "spec.md" in limited) == (
        True,
        True,
        False,
    )


@pytest.mark.parametrize(
    "argument", ["--output=out.txt", "-p", "HEAD", "main", "abc", "zz" * 8, ""]
)
def test_git_show_refuses_an_argument_that_is_no_commit_hash(
    tools: StageTools, repo: Path, argument: str
) -> None:
    answer = tools.git_show(argument)

    assert (answer.endswith("is no commit hash."), (repo / "out.txt").exists()) == (True, False)


def test_git_show_refuses_a_commit_that_is_not_in_the_history_of_the_staged_commit(
    repo: Path,
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    first = _git(repo, "rev-parse", "HEAD~1")
    older = StageTools(source=repo, sha=first)

    assert older.git_show(head).endswith("is not in the history of the staged commit.")


def test_git_show_answers_a_commit_that_does_not_exist_as_text(tools: StageTools) -> None:
    assert tools.git_show("0" * 12).endswith("is not in the history of the staged commit.")


def test_callers_lists_the_call_sites_of_a_symbol(tools: StageTools) -> None:
    assert tools.callers("hello_world").splitlines() == [
        "src/caller.py:3:value = hello_world()",
        "src/sample.py:1:def hello_world():",
    ]


def test_callers_matches_a_whole_name_and_refuses_text_that_is_no_name(tools: StageTools) -> None:
    assert (
        tools.callers("world"),
        tools.callers("a b"),
        tools.callers("--help"),
        tools.callers(""),
    ) == (
        "No call of world.",
        "The text a b is no symbol name.",
        "The text --help is no symbol name.",
        "The text  is no symbol name.",
    )


def test_file_symbols_lists_the_symbols_of_one_file_with_their_lines(tools: StageTools) -> None:
    lines = tools.file_symbols("src/sample.py").splitlines()

    assert [line.split(" ", 1)[0] for line in lines] == ["1:", "5:"]
    assert ["hello_world" in lines[0], "Greeter" in lines[1]] == [True, True]


def test_file_symbols_answers_a_bad_path_as_text(tools: StageTools, repo: Path) -> None:
    (repo / "data.bin").write_bytes(b"\0\1\2")
    (repo / "notes.txt").write_text("text", encoding="utf-8")

    assert (
        tools.file_symbols("../outside.py"),
        tools.file_symbols("src/missing.py"),
        tools.file_symbols("data.bin"),
        tools.file_symbols("notes.txt"),
        tools.file_symbols("src"),
    ) == (
        "The path ../outside.py is outside the repository.",
        "The checkout holds no file src/missing.py.",
        "The file data.bin has no symbols to read.",
        "The file notes.txt has no symbols to read.",
        "The checkout holds no file src.",
    )


def test_file_symbols_does_not_follow_a_link_out_of_the_repository(
    tools: StageTools, repo: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("def secret():\n    pass\n", encoding="utf-8")
    (repo / "src" / "link.py").symlink_to(outside)

    assert tools.file_symbols("src/link.py") == "The path src/link.py is outside the repository."


def test_repo_map_maps_a_directory_with_paths_from_the_top(tools: StageTools) -> None:
    mapped = tools.repo_map("src")

    assert ("src/sample.py" in mapped, "hello_world" in mapped, "Greeter" in mapped) == (
        True,
        True,
        True,
    )


def _many_files(repo: Path, count: int, symbols: int = 1) -> None:
    (repo / "many").mkdir(exist_ok=True)
    for number in range(count):
        body = "".join(f"def function_{number}_{n}():\n    pass\n" for n in range(symbols))
        (repo / "many" / f"m{number:02}.py").write_text(body, encoding="utf-8")


def test_repo_map_shows_a_line_for_each_file_and_says_when_files_are_left_out(
    tools: StageTools, repo: Path
) -> None:
    _many_files(repo, CONST_ROADMAP_STAGE_MAP_MAX_FILES + 5)

    lines = tools.repo_map("many").splitlines()

    assert lines[0] == "many/m00.py: function_0_0"
    assert (len(lines), lines[-1]) == (
        CONST_ROADMAP_STAGE_MAP_MAX_FILES + 1,
        "(more files are left out; map a subdirectory)",
    )


def test_repo_map_with_exactly_the_files_of_its_limit_says_nothing_is_left_out(
    tools: StageTools, repo: Path
) -> None:
    _many_files(repo, CONST_ROADMAP_STAGE_MAP_MAX_FILES)

    lines = tools.repo_map("many").splitlines()

    assert len(lines) == CONST_ROADMAP_STAGE_MAP_MAX_FILES
    assert "left out" not in lines[-1]


def test_repo_map_cuts_a_long_line_and_never_a_line_in_the_middle_of_the_answer(
    tools: StageTools, repo: Path
) -> None:
    _many_files(repo, CONST_ROADMAP_STAGE_MAP_MAX_FILES + 1, symbols=60)

    answer = tools.repo_map("many")

    lines = answer.splitlines()
    assert all(len(line) <= CONST_ROADMAP_STAGE_MAP_LINE_CHARS for line in lines[:-1])
    assert lines[0].endswith("...")
    assert len(answer) <= CONST_ROADMAP_REFINE_TOOL_MAX_CHARS


def test_the_lines_of_a_full_map_fit_one_tool_answer() -> None:
    longest = CONST_ROADMAP_STAGE_MAP_MAX_FILES * (CONST_ROADMAP_STAGE_MAP_LINE_CHARS + 1)

    assert longest + 60 <= CONST_ROADMAP_REFINE_TOOL_MAX_CHARS


def test_repo_map_of_the_top_maps_the_src_directory_and_a_test_directory_is_asked_for(
    tools: StageTools, repo: Path
) -> None:
    (repo / "tests").mkdir()
    (repo / "tests" / "test_sample.py").write_text("def test_it():\n    pass\n", encoding="utf-8")

    assert (
        tools.repo_map("").splitlines()[0].startswith("src/"),
        tools.repo_map("tests"),
    ) == (True, "tests/test_sample.py: test_it")


def test_repo_map_answers_a_bad_directory_as_text(tools: StageTools) -> None:
    assert (
        tools.repo_map("../outside"),
        tools.repo_map("nowhere"),
        tools.repo_map("src/sample.py"),
    ) == (
        "The path ../outside is outside the repository.",
        "The checkout holds no directory nowhere.",
        "The checkout holds no directory src/sample.py.",
    )


def test_read_spec_lists_the_capabilities_and_the_requirements(tools: StageTools) -> None:
    assert (
        tools.read_spec().splitlines(),
        tools.read_spec("sample").splitlines(),
    ) == (["sample"], ["The sample greets", "The sample leaves"])


def test_read_spec_returns_the_whole_text_of_one_requirement(tools: StageTools) -> None:
    text = tools.read_spec("sample", "The sample greets")

    assert text.splitlines() == [
        "### Requirement: The sample greets",
        "The sample SHALL greet.",
        "",
        "#### Scenario: A greeting",
        "- **WHEN** it runs",
        "- **THEN** it greets",
    ]


@pytest.mark.parametrize(
    ("capability", "requirement", "answer"),
    [
        ("../sample", "", "The text ../sample is no capability name."),
        ("sample/x", "", "The text sample/x is no capability name."),
        ("missing", "", "The checkout holds no spec missing."),
        ("sample", "Nothing", "The spec sample holds no requirement Nothing."),
    ],
)
def test_read_spec_answers_a_bad_argument_as_text(
    tools: StageTools, capability: str, requirement: str, answer: str
) -> None:
    assert tools.read_spec(capability, requirement) == answer


def test_a_binary_file_and_a_missing_file_are_answered_as_text(
    tools: StageTools, repo: Path
) -> None:
    (repo / "data.bin").write_bytes(b"\0\1\2")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "binary")
    fresh = StageTools(source=repo, sha=_git(repo, "rev-parse", "HEAD"))

    assert (fresh.read_file("data.bin"), fresh.read_file("src/none.py")) == (
        "The file data.bin is binary.",
        "The commit holds no file src/none.py.",
    )


def test_no_tool_raises_on_a_hostile_argument(tools: StageTools) -> None:
    hostile = "\0--output=x\n../"

    answers = [
        tools.git_log(hostile),
        tools.git_show(hostile),
        tools.callers(hostile),
        tools.file_symbols(hostile),
        tools.repo_map(hostile),
        tools.read_spec(hostile, hostile),
    ]

    assert all(isinstance(answer, str) and answer for answer in answers)


def test_read_spec_without_the_tool_says_so(repo: Path) -> None:
    bare = StageTools(source=repo, sha=_git(repo, "rev-parse", "HEAD"))

    assert bare.read_spec("sample") == "OpenSpec is not installed, so no spec can be read."


def test_the_checkout_of_the_staged_commit_with_no_change_has_no_problem(
    tools: StageTools,
) -> None:
    assert tools.checkout_problem() is None


def test_a_checkout_with_a_change_or_a_file_that_is_not_tracked_has_a_problem(
    tools: StageTools, repo: Path
) -> None:
    (repo / "untracked.py").write_text("def untracked_only():\n    pass\n", encoding="utf-8")
    untracked = tools.checkout_problem()
    (repo / "untracked.py").unlink()
    (repo / "src" / "sample.py").write_text("changed = 1\n", encoding="utf-8")

    assert (
        "not committed" in str(untracked),
        "not committed" in str(tools.checkout_problem()),
    ) == (
        True,
        True,
    )


def test_a_checkout_at_another_commit_has_a_problem(tools: StageTools, repo: Path) -> None:
    older = StageTools(source=repo, sha=_git(repo, "rev-parse", "HEAD~1"))

    assert "not at the staged commit" in str(older.checkout_problem())


def test_read_file_refuses_a_file_over_the_size_limit_without_reading_it(repo: Path) -> None:
    big = "x" * 100 + "\n"
    _commit(repo, "big", {"big.txt": big * (CONST_ROADMAP_INVESTIGATION_MAX_BLOB_BYTES // 100)})
    fresh = StageTools(source=repo, sha=_git(repo, "rev-parse", "HEAD"))

    assert fresh.read_file("big.txt") == "The file big.txt is too large to read."


def test_read_file_numbers_only_the_lines_it_returns(repo: Path) -> None:
    lines = CONST_ROADMAP_REFINE_TOOL_MAX_LINES + 50
    _commit(repo, "long", {"long.txt": "".join(f"line {n}\r\n" for n in range(1, lines + 1))})
    fresh = StageTools(source=repo, sha=_git(repo, "rev-parse", "HEAD"))

    whole = fresh.read_file("long.txt").splitlines()
    ranged = fresh.read_file("long.txt", 130, 132).splitlines()
    past = fresh.read_file("long.txt", lines + 5)

    assert (whole[0], whole[CONST_ROADMAP_REFINE_TOOL_MAX_LINES - 1], whole[-1]) == (
        "1: line 1",
        f"{CONST_ROADMAP_REFINE_TOOL_MAX_LINES}: line {CONST_ROADMAP_REFINE_TOOL_MAX_LINES}",
        "(more lines are left out)",
    )
    assert (ranged, past) == (
        ["130: line 130", "131: line 131", "132: line 132"],
        f"The file long.txt has no lines from line {lines + 5}.",
    )


def test_search_code_and_callers_stop_at_the_matches_a_tool_answer_can_hold(repo: Path) -> None:
    many = CONST_ROADMAP_REFINE_TOOL_MAX_LINES * 3
    _commit(repo, "many", {"many.py": "".join("call_me()\n" for _ in range(many))})
    fresh = StageTools(source=repo, sha=_git(repo, "rev-parse", "HEAD"))

    searched = fresh.search_code("call_me").splitlines()
    called = fresh.callers("call_me").splitlines()

    assert (len(searched), len(called)) == (
        CONST_ROADMAP_REFINE_TOOL_MAX_LINES + 1,
        CONST_ROADMAP_REFINE_TOOL_MAX_LINES + 1,
    )
    assert (searched[-1], called[-1]) == ("(more lines are left out)",) * 2


@pytest.mark.live("openspec")
def test_read_spec_reads_what_the_real_openspec_prints(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")

    with isolated_openspec() as tool:
        live = StageTools(source=repo, sha=sha, openspec=tool)
        answers = (
            live.read_spec().splitlines(),
            live.read_spec("sample").splitlines(),
            live.read_spec("sample", "The sample greets").splitlines()[:4],
            live.read_spec("missing"),
        )

    assert answers == (
        ["sample"],
        ["The sample greets", "The sample leaves"],
        [
            "### Requirement: The sample greets",
            "The sample SHALL greet.",
            "",
            "#### Scenario: A greeting",
        ],
        "The checkout holds no spec missing.",
    )
