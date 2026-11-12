"""The reason of a refused or failed verification command is safe to show (#3263).

The stop reason of a step goes to a comment on the item, and the problem of the stage gate goes
back to the model. Both name the command, and the command comes from a `tasks.md` or from a reply
of a model. So the command is escaped and cut where it is named, for the step and for the gate, and
a command of any program has a limit on its words. These tests read the real path: the outcome of
`run_step`, `commands_failure` and `form_problems`.
"""

from __future__ import annotations

import subprocess
import unicodedata
from pathlib import Path

import pytest

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS
from devops_cli.roadmap.implement.implement_shell_policy import fill_prompt, verification_problem
from devops_cli.roadmap.implement.implement_step import StepStatus, commands_failure, run_step
from devops_cli.roadmap.stage.stage_change import StageGroup
from devops_cli.roadmap.stage.stage_form import form_problems
from tests.support.builders import make_stage_proposal
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    DOCS,
    TASKS,
    TASKS_PATH,
    WINDOW,
    command_text,
    git,
    make_checkout,
    programs_run,
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

# The categories that a person or a terminal reads as a command and not as text: control and format
# characters (ESC, NEL, a bidi override), and the line and paragraph separators.
HOSTILE = frozenset({"Cc", "Cf", "Zl", "Zp"})
LIMIT = 2000


def _hostile(text: str) -> list[str]:
    return [c for c in text if unicodedata.category(c) in HOSTILE]


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    return make_checkout(tmp_path)


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _group(verify: str) -> StageGroup:
    base = make_stage_proposal().groups[0].model_dump()
    return StageGroup.model_validate({**base, "verify": verify})


# ── The command is escaped where a reason names it ────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "curl \x1b[31mRED",
        "curl \x0bvt",
        "curl a\x85b",
        "curl a\u2028b",
        "curl \u202eevil @octocat",
        "curl a\x00b",
        "curl a\x7fb",
        "! rm \x00 x",
        "! git grep -n 'a\nb' src/",
        "! git grep -n a\x85b src/",
    ],
)
def test_a_refused_command_is_named_in_the_reason_with_no_control_character(
    checkout: Path, programs: ProcessFake, command: str
) -> None:
    reason = commands_failure(checkout, [command])

    assert reason is not None
    assert _hostile(reason) == []
    assert reason.isascii()


def test_the_reason_shows_the_escapes_of_a_command_that_is_refused() -> None:
    reason = commands_failure(Path("."), ["curl \x1b[31mRED\u202e @octocat"])

    assert reason == (
        "The verification command curl \\x1b[31mRED\\u202e @octocat is refused: "
        "`curl` is not one of: uv, ruff, mypy, grep, cat, ls, head, tail, wc, find, openspec, "
        "devops."
    )


def test_a_command_that_fails_is_named_in_the_reason_with_no_control_character(
    checkout: Path, programs: ProcessFake
) -> None:
    command = "uv run devops ci \x1b[31m\u202e"
    programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci"),
        ProcessAnswer(returncode=1, stdout="bad\n"),
    )

    reason = commands_failure(checkout, [command])

    assert reason is not None
    assert reason.startswith("uv run devops ci \\x1b[31m\\u202e exited with status 1.")
    assert _hostile(reason.splitlines()[0]) == []


def test_a_command_that_times_out_is_named_in_the_reason_with_no_control_character(
    checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci"),
        ProcessAnswer(side_effect=subprocess.TimeoutExpired(cmd="uv", timeout=1)),
    )

    reason = commands_failure(checkout, ["uv run devops ci \x1b[31m"])

    assert reason is not None
    assert reason.startswith("uv run devops ci \\x1b[31m ran out of time")
    assert _hostile(reason) == []


def test_the_outcome_of_a_step_holds_no_control_character_of_a_verification_line(
    implement_store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    """The real path: a `tasks.md` line to `outcome.reason`, which the job posts to the item."""
    tasks = TASKS.replace(DOCS, "curl \x1b[31mRED\u202e evil @octocat")
    checkout = make_checkout(tmp_path, tasks)
    ticked = tasks.replace("- [ ] Add", "- [x] Add")
    script = ModelScript(tool_calls(write_call(TASKS_PATH, ticked)), say("Done."))

    outcome = run_step(
        implement_store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW
    )

    assert outcome.status is StepStatus.STOPPED
    assert outcome.reason.startswith(
        "The verification command curl \\x1b[31mRED\\u202e evil @octocat is refused: "
    )
    assert _hostile(outcome.reason) == []


# ── The gate names the command escaped and cut ────────────────────────────────────────────


@pytest.mark.parametrize(
    "verify",
    [
        "curl \x1b[31mRED",
        "! git grep -n 'a\x00b' src/",
        "! git grep -n x src/ \u202e",
        "uv run \x85",
    ],
)
def test_the_problem_of_the_gate_holds_no_control_character(verify: str) -> None:
    problems = form_problems([_group(verify)])

    assert problems != []
    assert _hostile("".join(problems)) == []


@pytest.mark.parametrize(
    "verify", ["! git grep -n " + "a" * 300000 + " src/", "curl " + "a" * 300000]
)
def test_the_problem_of_the_gate_is_cut_to_the_limit(verify: str) -> None:
    (problem,) = form_problems([_group(verify)])

    assert len(problem) < LIMIT + 400


# ── A limit on every verification command ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "grep -n zz " + "a" * 300000 + " src/",
        "uv run devops ci test " + "a" * 300000,
        "! git grep -n " + "a" * 300000 + " src/",
        "git status " + "a " * 3000,
    ],
    ids=["grep", "uv-run-devops", "negative-search", "many-words"],
)
def test_a_long_verification_command_of_any_program_is_refused_and_starts_no_process(
    checkout: Path, programs: ProcessFake, command: str
) -> None:
    assert verification_problem(command) == "it is longer than 2000 characters"
    reason = commands_failure(checkout, [command])

    assert reason is not None
    assert reason.endswith("is refused: it is longer than 2000 characters.")
    assert len(reason) < LIMIT + 200
    assert programs.calls == []


def test_the_words_of_a_command_may_hold_2000_characters_and_not_2001() -> None:
    at = "grep " + "a" * 1996
    over = "grep " + "a" * 1997

    assert (verification_problem(at), verification_problem(over)) == (
        None,
        "it is longer than 2000 characters",
    )
    assert CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS == LIMIT


# ── The cuts and the escapes of a word in a reason ────────────────────────────────────────


def test_a_literal_of_60_escaped_characters_is_shown_whole_and_61_is_cut() -> None:
    sixty = "x;" * 30
    sixty_one = sixty + "y"

    assert verification_problem(f"! git grep -n '{sixty}' src/") == (
        f"the text `{sixty}` is not a literal of letters, digits, spaces and the signs "
        "_ . : / = @ + , # % ~ -"
    )
    assert verification_problem(f"! git grep -n '{sixty_one}' src/") == (
        f"the text `{sixty}...` is not a literal of letters, digits, spaces and the signs "
        "_ . : / = @ + , # % ~ -"
    )


def test_an_option_word_and_the_first_word_are_shown_escaped() -> None:
    assert verification_problem("! git grep -\x1b[31m name src/") == (
        "the option `-\\x1b[31m` is not allowed (the options are -n -I -F -i -w -l -c -q)"
    )
    assert verification_problem("cu\x1brl x") == (
        "`cu\\x1brl` is not one of: uv, ruff, mypy, grep, cat, ls, head, tail, wc, find, "
        "openspec, devops"
    )
    assert verification_problem("! git grep -n x 'a\x1bb'") == (
        "the word `a\\x1bb` is not a path of the checkout"
    )


def test_a_refused_command_of_2000_characters_is_named_whole_and_one_more_is_cut(
    checkout: Path,
) -> None:
    at = "curl " + "a" * 1995
    over = "curl " + "a" * 1996
    refused = "is refused: `curl` is not one of:"

    reason_at = commands_failure(checkout, [at])
    reason_over = commands_failure(checkout, [over])

    assert reason_at is not None
    assert reason_at.startswith(f"The verification command {at} {refused}")
    assert reason_over is not None
    assert reason_over.startswith(f"The verification command {over[:LIMIT]}... {refused}")


# ── The prompt says what the step does with a bang command ────────────────────────────────


def test_step_5_of_the_prompt_gives_both_parts_of_the_sentence_about_a_bang_command() -> None:
    prompt = fill_prompt(load_task_prompt("roadmap_implement_step.md"))

    assert "the step runs it itself after your run, and the shell refuses `!`" in prompt
    assert "To see its result now, run the `git grep` form that the table below gives." in prompt


def test_the_programs_run_stay_empty_for_a_refused_command(
    checkout: Path, programs: ProcessFake
) -> None:
    commands_failure(checkout, ["curl x", "! git grep -O x src/"])

    assert programs_run(programs, "curl") == []


# ── The output of a command is escaped too ───────────────────────────────────────────────

OUTPUT = "bad \x1b[31mred\u202e @octocat\x85 end\x00"


def test_the_output_of_a_failed_command_is_in_the_reason_with_no_control_character(
    checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci"),
        ProcessAnswer(returncode=1, stdout=f"{OUTPUT}\nsecond line\n"),
    )

    reason = commands_failure(checkout, ["uv run devops ci"])

    assert reason is not None
    assert _hostile(reason.replace("\n", " ")) == []
    # `splitlines` of the output breaks the line at the NEL, and each part is escaped.
    assert reason.splitlines()[1:] == [
        "bad \\x1b[31mred\\u202e @octocat",
        " end\\x00",
        "second line",
    ]


def test_the_matching_lines_of_a_negative_search_are_in_the_reason_with_no_control_character(
    checkout: Path, programs: ProcessFake
) -> None:
    # A NUL byte makes git call the file binary, so the line has none.
    line = f"foo {OUTPUT}".replace("\x00", "")
    (checkout / "src" / "hostile.py").write_text(f"{line}\n", encoding="utf-8")
    git(checkout, "add", "-A")

    reason = commands_failure(checkout, ["! git grep -n foo -- src"])

    assert reason is not None
    assert _hostile(reason.replace("\n", " ")) == []
    # `splitlines` breaks the matching line at the NEL, and each part is escaped.
    assert reason.splitlines()[1:] == [
        "src/hostile.py:1:foo bad \\x1b[31mred\\u202e @octocat",
        " end",
    ]


def test_the_outcome_of_a_step_holds_no_control_character_of_the_output_of_a_command(
    implement_store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    checkout = make_checkout(tmp_path)
    programs.answer(
        lambda call: command_text(call) == DOCS,
        ProcessAnswer(returncode=1, stdout=f"{OUTPUT}\n"),
    )
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = run_step(
        implement_store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW
    )

    assert outcome.status is StepStatus.STOPPED
    assert _hostile(outcome.reason.replace("\n", " ")) == []
    assert "bad \\x1b[31mred" in outcome.reason


# ── A word that cannot be an argument is refused ─────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "grep a\x00b src/",
        "uv run devops ci a\x00b",
        "git grep \ud800 -- src",
        "! git grep -n a\x00b src/",
    ],
    ids=["nul-grep", "nul-uv", "surrogate", "nul-search"],
)
def test_a_word_with_a_nul_byte_or_a_lone_surrogate_is_refused_not_raised(
    checkout: Path, programs: ProcessFake, command: str
) -> None:
    problem = verification_problem(command)
    reason = commands_failure(checkout, [command])

    assert problem is not None
    assert reason is not None
    assert reason.endswith(f"is refused: {problem}.")
    assert programs.calls == []
    assert _hostile(reason) == []


def test_the_reason_for_a_nul_byte_says_what_is_wrong() -> None:
    assert verification_problem("grep a\x00b src/") == (
        "a word holds a NUL byte or a character that cannot be encoded"
    )


def test_the_gate_refuses_a_command_with_a_nul_byte() -> None:
    (problem,) = form_problems([_group("uv run devops ci a\x00b")])

    assert "a word holds a NUL byte" in problem
    assert _hostile(problem) == []


def test_the_problem_for_a_backtick_names_the_command_escaped_and_cut() -> None:
    problems = form_problems([_group("uv run devops ci `x\x1b[31m" + "a" * 3000)])

    (problem,) = [text for text in problems if "holds a backtick" in text]
    assert _hostile(problem) == []
    assert "\\x1b[31m" in problem
    assert len(problem) < LIMIT + 400
