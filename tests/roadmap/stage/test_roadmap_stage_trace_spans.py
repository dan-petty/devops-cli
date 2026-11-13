"""The trace gate reads a path in the forms that the stage prompt asks a plan to cite.

A plan cites a line as `path:line:text` and a symbol as `path:def name`. The trace gate judges the
path of such a citation, and a word `read` inside a quoted line is no claim that the run read a file.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap.agent_run import TraceFacts
from devops_cli.roadmap.stage.stage_change import StageProposal, check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.tools import HOLDER_STAGE_EXTENDED, tool_names
from tests.support.builders import make_stage_proposal

CONSTANTS = "src/devops_cli/config/constants.py"
TREE = StagedTree(["src/devops_cli/sample.py", CONSTANTS])
READ_CONSTANTS = TraceFacts(tools=frozenset({"read_file"}), paths=frozenset({CONSTANTS}))


def _problems(sentence: str, trace: TraceFacts | None) -> list[str]:
    plan: StageProposal = make_stage_proposal(feasibility=[sentence])
    # An empty registry keeps the registry gate from parsing each test file of the repository.
    keywords: dict[str, Any] = {"trace": trace, "registry": []}
    return check_proposal(plan, ["comment-thread"], TREE, **keywords)


@pytest.mark.parametrize(
    "span",
    [
        f"{CONSTANTS}:308:DEFAULT_LIMIT = 60",
        f"{CONSTANTS}:def load_constants",
        f"{CONSTANTS}:class Limits",
        f"./{CONSTANTS}",
        "src/devops_cli/config/constants.py",
        "config/constants.py",
        "constants.py",
    ],
)
def test_a_claim_in_a_citation_form_of_a_read_path_passes(span: str) -> None:
    assert _problems(f"The run read `{span}` and found the line.", READ_CONSTANTS) == []


@pytest.mark.parametrize(
    "span",
    [
        "src/devops_cli/config/other.py:12:value = 1",
        "src/devops_cli/config/other.py:def other",
        "src/other/constants.py",
        "other_constants.py",
    ],
)
def test_a_claim_in_a_citation_form_of_an_unread_path_is_refused(span: str) -> None:
    problems = _problems(f"The run read `{span}` and found the line.", READ_CONSTANTS)

    assert len(problems) == 1
    assert "did not read" in problems[0]


def test_the_refusal_names_the_path_and_not_the_whole_citation() -> None:
    other = "src/devops_cli/config/other.py"

    problems = _problems(f"The run read `{other}:12:value = 1` and found it.", READ_CONSTANTS)

    assert other in problems[0]
    assert "value = 1" not in problems[0]


def test_the_word_read_in_a_quoted_line_is_no_claim_of_a_read() -> None:
    sentence = f'The probe shows `{CONSTANTS}:308:(("ai", "read"), 60.0, True)` for the limit.'

    assert _problems(sentence, TraceFacts()) == []


def test_the_name_of_the_read_tool_in_a_code_span_still_makes_the_claim() -> None:
    problems = _problems("The run called `read_file` on `src/devops_cli/other.py`.", TraceFacts())

    assert len(problems) == 1
    assert "src/devops_cli/other.py" in problems[0]


# The other citation forms that plans write: a line, a line range and a tool call (#4463).
@pytest.mark.parametrize(
    "span",
    [
        f"{CONSTANTS}:308",
        f"{CONSTANTS}:300-320",
        f"{CONSTANTS}:300-320:DEFAULT_LIMIT = 60",
        f"./{CONSTANTS}:300-320",
        f"read_file {CONSTANTS}",
        f"read_file {CONSTANTS}:300-320",
        "file_symbols config/constants.py",
        f'read_file("{CONSTANTS}", 60, 80)',
        f"read_file('{CONSTANTS}', 60, 80)",
        f'read_file( "{CONSTANTS}" )',
        f'read_file("./{CONSTANTS}")',
        f'read_file("{CONSTANTS}:300-320")',
    ],
)
def test_a_line_or_a_tool_call_citation_of_a_read_path_passes(span: str) -> None:
    assert _problems(f"The run read `{span}` and found the line.", READ_CONSTANTS) == []


@pytest.mark.parametrize("tool", sorted(tool_names(HOLDER_STAGE_EXTENDED)))
def test_each_toolbox_tool_name_before_a_read_path_passes(tool: str) -> None:
    assert _problems(f"The run read `{tool} {CONSTANTS}` and found it.", READ_CONSTANTS) == []


@pytest.mark.parametrize(
    "span",
    [
        "src/devops_cli/config/other.py:12",
        "src/devops_cli/config/other.py:10-20",
        "read_file src/devops_cli/config/other.py",
        "read_file src/devops_cli/config/other.py:10-20",
        'read_file("src/devops_cli/config/other.py", 60, 80)',
        "read_file('src/devops_cli/config/other.py', 60, 80)",
        "src/devops_cli/config/",
    ],
)
def test_a_line_or_a_tool_call_citation_of_an_unread_path_is_refused(span: str) -> None:
    problems = _problems(f"The run read `{span}` and found the line.", READ_CONSTANTS)

    assert len(problems) == 1
    assert "did not read" in problems[0]


def test_a_call_of_a_word_that_is_no_toolbox_tool_stays_in_the_path() -> None:
    span = f'cat("{CONSTANTS}")'

    problems = _problems(f"The run read `{span}` and found it.", READ_CONSTANTS)

    assert len(problems) == 1
    assert span in problems[0]


def test_the_refusal_of_a_tool_call_names_the_path() -> None:
    other = "src/devops_cli/config/other.py"

    problems = _problems(
        f'The run read `read_file("{other}", 60, 80)` and found it.', READ_CONSTANTS
    )

    assert f"`{other}`" in problems[0]


def test_a_word_that_is_no_toolbox_tool_stays_in_the_path() -> None:
    problems = _problems(f"The run read `cat {CONSTANTS}` and found it.", READ_CONSTANTS)

    assert len(problems) == 1
    assert f"cat {CONSTANTS}" in problems[0]


def test_the_refusal_of_a_line_range_names_the_path() -> None:
    other = "src/devops_cli/config/other.py"

    problems = _problems(f"The run read `{other}:10-20` and found it.", READ_CONSTANTS)

    assert f"`{other}`" in problems[0]


# The form of a `read_file` call with its start and end line after the path, as the fix-plan run
# on #5390 wrote it on 2026-11-13: `read_file src/devops_cli/config/constants.py 3915 3935` (#5391).
@pytest.mark.parametrize("lines", ["3915 3935", "3915"])
def test_the_line_arguments_after_a_read_path_are_no_part_of_the_path(lines: str) -> None:
    sentence = f"`read_file {CONSTANTS} {lines}` gives the limit of the point."

    assert _problems(sentence, READ_CONSTANTS) == []


def test_the_refusal_of_a_read_with_line_arguments_names_the_path() -> None:
    other = "src/devops_cli/config/other.py"

    problems = _problems(f"`read_file {other} 3915 3935` gives the limit.", READ_CONSTANTS)

    assert len(problems) == 1
    assert f"`{other}` was read" in problems[0]


def test_numbers_after_a_word_that_is_no_toolbox_tool_stay_in_the_path() -> None:
    problems = _problems(f"The run read `cat {CONSTANTS} 3915 3935` and found it.", READ_CONSTANTS)

    assert len(problems) == 1
    assert f"cat {CONSTANTS} 3915 3935" in problems[0]


@pytest.mark.parametrize(
    ("span", "listed"),
    [
        ("tests/telemetry/", "tests/telemetry"),
        ("tests/telemetry/", "tests/telemetry/"),
        ("tests/telemetry", "tests/telemetry/"),
    ],
)
def test_a_directory_with_a_trailing_slash_passes_when_the_run_listed_it(
    span: str, listed: str
) -> None:
    trace = TraceFacts(tools=frozenset({"list_files"}), paths=frozenset({listed}))

    assert _problems(f"The run read `{span}` and found the tests.", trace) == []


PROBE_LINE = "The path `src/devops_cli/other.py` is a file of the staging commit."


def _probed(sentence: str) -> list[str]:
    plan: StageProposal = make_stage_proposal(feasibility=[sentence])
    keywords: dict[str, Any] = {"trace": TraceFacts(), "probes": [PROBE_LINE], "registry": []}
    return check_proposal(plan, ["comment-thread"], TREE, **keywords)


@pytest.mark.parametrize(
    "sentence",
    [
        f"The probe line reads: {PROBE_LINE}",
        f'The probe line reads, word for word: "{PROBE_LINE}"',
        f"The probe reads, word for word: {PROBE_LINE.removesuffix('.')}, so the path holds.",
    ],
)
def test_a_quoted_probe_line_is_no_claim_of_a_read(sentence: str) -> None:
    assert [problem for problem in _probed(sentence) if "did not read" in problem] == []


def test_a_read_claim_beside_a_quoted_probe_line_is_still_refused() -> None:
    problems = _probed(f"I read `src/devops_cli/wrong.py`, and the probe says: {PROBE_LINE}")

    assert len(problems) == 1
    assert "`src/devops_cli/wrong.py`" in problems[0]


def test_a_probe_line_that_the_plan_does_not_quote_changes_no_claim() -> None:
    problems = _probed("I read `src/devops_cli/other.py` and found the function.")

    assert len(problems) == 2
    assert any("`src/devops_cli/other.py` was read" in p for p in problems)


# A search match shows one line of a file: `search_code` and `callers` answer `path:line:content`
# (#4495). A citation of that line is seen, and a claim of the whole file or of a range is not.
MATCHED = "tests/roadmap/test_amend.py"
SEARCHED = TraceFacts(tools=frozenset({"search_code"}), lines=frozenset({f"{MATCHED}:5"}))


@pytest.mark.parametrize(
    ("span", "refused"),
    [
        (f"{MATCHED}:5:from x import y", False),
        (f"{MATCHED}:5", False),
        ("roadmap/test_amend.py:5:from x import y", False),
        (f"search_code {MATCHED}:5", False),
        (MATCHED, True),
        (f"{MATCHED}:6:import z", True),
        (f"{MATCHED}:1-9", True),
        (f"{MATCHED}:def test_amend", True),
        ("tests/roadmap/test_other.py:5", True),
    ],
)
def test_a_search_match_supports_a_citation_of_its_line_only(span: str, refused: bool) -> None:
    problems = _problems(f"The run read `{span}` in the search answer.", SEARCHED)

    assert any("did not read" in problem for problem in problems) is refused
