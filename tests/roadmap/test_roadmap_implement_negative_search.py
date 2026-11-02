"""A negative search is a verification command of an implement step (#3263).

The stage gate admits `! git grep -n <name> src/ tests/` as the check that a name is gone. The step
runs a verification command as a list of words, never through a shell, so the form must be a fixed
shape that the step reads itself: a command that is `!` followed by anything else is refused. The
checkout is a real git repository and git runs for real on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_SEARCH_CHARS
from devops_cli.roadmap.implement_shell_policy import (
    IMPLEMENT_ALLOWED_PROGRAMS,
    NEGATIVE_SEARCH_LITERAL_SIGNS,
    NEGATIVE_SEARCH_OPTION_LETTERS,
    verification_problem,
)
from devops_cli.roadmap.implement_step import commands_failure
from devops_cli.roadmap.stage_change import StageGroup
from devops_cli.roadmap.stage_form import form_problems
from devops_cli.roadmap.step_files import parse_task_groups
from tests.support.builders import make_stage_proposal
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import make_checkout, programs_run

pytestmark = pytest.mark.usefixtures("keyring_store")

GONE = "! git grep -n absent_name src/ tests/"
FOUND = "! git grep -n hello src/ tests/"


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    return make_checkout(tmp_path)


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def test_a_negative_search_that_finds_nothing_passes(checkout: Path, programs: ProcessFake) -> None:
    assert commands_failure(checkout, [GONE]) is None
    assert programs_run(programs, "git") == ["git grep -n absent_name -- src/ tests/"]


def test_a_negative_search_that_finds_a_match_stops_the_step_with_the_match(
    checkout: Path, programs: ProcessFake
) -> None:
    assert commands_failure(checkout, [FOUND]) == (
        f"{FOUND} found a match, so the name is not gone.\n"
        "src/sample.py:4:def hello(name: str) -> str:\n"
        'src/sample.py:6:    return f"hello {name}"'
    )


def test_a_path_is_never_read_as_a_revision(checkout: Path, programs: ProcessFake) -> None:
    """Git reads a word after the literal as a revision when no path has that name. The step puts
    `--` before the paths, so a path that is no file gives exit 1, not an error."""
    assert commands_failure(checkout, ["! git grep -n hello missing/"]) is None
    assert programs_run(programs, "git") == ["git grep -n hello -- missing/"]


def test_a_negative_search_that_fails_to_run_is_no_pass(
    checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(("git", "grep"), ProcessAnswer(returncode=128, stderr="fatal: bad revision\n"))

    reason = commands_failure(checkout, [GONE])

    assert reason is not None
    assert reason.startswith(f"{GONE} exited with status 128.")


START = "it does not start with `! git grep`"
OPTIONS = "(the options are -n -I -F -i -w -l -c -q)"


def _literal(word: str) -> str:
    return f"the text `{word}` is not a literal of letters, digits, spaces and the signs _ . : / = @ + , # % ~ -"


def _path(word: str) -> str:
    return f"the word `{word}` is not a path of the checkout"


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("! rm -rf src/", START),
        ("! git log", START),
        ("! git -c core.pager=x grep -n name src/", START),
        ("! uv run devops ci", START),
        ("!", START),
        ("! git grep -n name src/ | cat", _path("|")),
        ("! git grep -n name src/ ; rm -rf tests/", _path(";")),
        ("! git grep -n name src/ && ls", _path("&&")),
        ("! git grep -n name src/ > out.txt", _path(">")),
        ("! git grep -n name src/; ls", _path("src/;")),
        ("! git grep -n name '(src/)'", _path("(src/)")),
        ("! git grep -n name $HOME", _path("$HOME")),
        ("! git grep -n 'a;b' src/", _literal("a;b")),
        ("! git grep -n '$(id)' src/", _literal("$(id)")),
        ("! git grep -n 'a|b' src/", _literal("a|b")),
        ("! git grep -n 'a>b' src/", _literal("a>b")),
        ("! git grep -n '`id`' src/", _literal("`id`")),
        ("! git grep -n 'a*' src/", _literal("a*")),
        ("! git grep -n '' src/", _literal("")),
        ("! git grep -n \uff46oo src/", _literal("\\uff46oo")),
        ("! git grep -n caf\u00e9 src/", _literal("caf\\xe9")),
        ("! git grep -n foo \uff53rc/", _path("\\uff53rc/")),
        ("! git grep -n foo src\u00e9/", _path("src\\xe9/")),
        ("! git grep -n 'a\x00b' src/", _literal("a\\x00b")),
        ("! git grep -n 'a\tb' src/", _literal("a\\tb")),
        ("! git grep -n foo 'a\x00b'", _path("a\\x00b")),
        ("! git grep -n foo 'src/\\x'", _path("src/\\\\x")),
        ("! git grep -O name src/", f"the option `-O` is not allowed {OPTIONS}"),
        (
            "! git grep --open-files-in-pager=cat name src/",
            f"the option `--open-files-in-pager=cat` is not allowed {OPTIONS}",
        ),
        ("! git grep --no-index -n name src/", f"the option `--no-index` is not allowed {OPTIONS}"),
        ("! git grep -f patterns.txt src/", f"the option `-f` is not allowed {OPTIONS}"),
        ("! git grep --ext-grep name src/", f"the option `--ext-grep` is not allowed {OPTIONS}"),
        ("! git grep -e name src/", f"the option `-e` is not allowed {OPTIONS}"),
        ("! git grep -nP name src/", f"the option `-nP` is not allowed {OPTIONS}"),
        ("! git grep -n -- name src/", f"the option `--` is not allowed {OPTIONS}"),
        ("! git grep -n", "it gives no text to search"),
        ("! git grep -n name", "it gives no path"),
        ("! git grep -n name --", "it gives no path"),
        ("! git grep -n name /etc", _path("/etc")),
        ("! git grep -n name ../other", _path("../other")),
        ("! git grep -n name src/../../x", _path("src/../../x")),
        ("! git grep -n name :(top)src", _path(":(top)src")),
        ("! git grep -n name src/ -O", _path("-O")),
        ("! git grep -n name -- src/ -- tests/", _path("--")),
    ],
)
def test_a_negative_search_outside_the_fixed_shape_is_refused_and_starts_no_process(
    checkout: Path, programs: ProcessFake, command: str, reason: str
) -> None:
    assert commands_failure(checkout, [command]) == (
        f"The verification command {command} is refused: {reason}."
    )
    assert programs_run(programs, "git") == []


def test_a_word_that_holds_a_line_break_is_shown_escaped_and_cut(
    checkout: Path, programs: ProcessFake
) -> None:
    command = "! git grep -n 'a\nb' src/"

    assert verification_problem(command) == _literal("a\\nb")
    assert verification_problem("! git grep -n '" + "x;" * 100 + "' src/") == _literal(
        ("x;" * 100)[:60] + "..."
    )
    assert programs_run(programs, "git") == []


def test_a_search_longer_than_the_limit_is_refused_and_starts_no_process(
    checkout: Path, programs: ProcessFake
) -> None:
    """A word of 300000 characters made `execve` fail with E2BIG, and the step crashed. The limit
    counts the characters of all the words, and the stop shows the command cut to the limit."""
    limit = CONST_ROADMAP_IMPLEMENT_SEARCH_CHARS
    words = len("!") + len("git") + len("grep") + len("-n") + len("src/")
    long = f"! git grep -n {'a' * 300000} src/"
    edge = f"! git grep -n {'a' * (limit - words)} src/"

    assert commands_failure(checkout, [long]) == (
        f"The verification command {long[:limit]}... is refused: "
        f"it is longer than {limit} characters."
    )
    assert commands_failure(checkout, [edge + "b"]) is not None
    assert programs_run(programs, "git") == []
    assert commands_failure(checkout, [edge]) is None
    assert programs_run(programs, "git") == [f"git grep -n {'a' * (limit - words)} -- src/"]


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        (
            "curl http://example.com",
            "`curl` is not one of: " + ", ".join(IMPLEMENT_ALLOWED_PROGRAMS),
        ),
        ("uv run 'devops", "it is not a valid command line"),
        ("", "it is not a valid command line"),
    ],
)
def test_the_step_refuses_a_command_with_the_reason_that_the_gate_gives(
    checkout: Path, programs: ProcessFake, command: str, reason: str
) -> None:
    assert verification_problem(command) == reason
    assert commands_failure(checkout, [command]) == (
        f"The verification command {command} is refused: {reason}."
    )
    assert programs_run(programs, "curl") == []


@pytest.mark.parametrize(
    "command",
    [
        "uv run devops ci",
        "devops docs check",
        "openspec validate x",
        "curl http://example.com",
        "uv run 'devops",
        GONE,
        FOUND,
        "! rm -rf src/",
        "! git grep -O name src/",
        "! git grep -n name",
        "!git grep -n name src/",
    ],
)
def test_the_step_refuses_exactly_the_commands_that_the_gate_reason_covers(
    checkout: Path, programs: ProcessFake, command: str
) -> None:
    """The step and the gate read one function, so no command is refused by one side only."""
    problem = verification_problem(command)
    failure = commands_failure(checkout, [command])

    refused = f"The verification command {command} is refused: {problem}."
    assert (problem is None) == (failure != refused)


def test_every_verify_form_that_the_gate_admits_is_a_command_that_the_step_runs(
    checkout: Path, programs: ProcessFake
) -> None:
    admitted = [
        "uv run devops ci",
        "uv run devops ci test tests/roadmap/test_stage.py",
        "uv run devops docs check",
        GONE,
        "! git grep -n -w old_name src/ tests/",
        "! git grep -nI -F old_name -- src/ tests/",
        "! git grep -i 'old name' src/devops_cli/",
    ]
    base = make_stage_proposal().groups[0].model_dump()
    for verify in admitted:
        group = StageGroup.model_validate({**base, "verify": verify})
        assert form_problems([group]) == [], verify
        assert commands_failure(checkout, [verify]) is None, verify


def test_the_stage_prompt_gives_the_options_and_the_signs_that_the_step_reads() -> None:
    prompt = load_task_prompt("roadmap_stage_change.md")

    options = " ".join(f"-{letter}" for letter in NEGATIVE_SEARCH_OPTION_LETTERS)
    assert (f"`{options}`" in prompt, f"`{NEGATIVE_SEARCH_LITERAL_SIGNS}`" in prompt) == (
        True,
        True,
    )


def test_a_negative_search_in_a_verification_line_is_a_command_of_the_group_and_the_step_runs_it(
    checkout: Path, programs: ProcessFake
) -> None:
    tasks = f"## 1. Remove it\n\n- [ ] Remove `old_name`\n  - Verification: `{GONE}`\n"

    (group,) = parse_task_groups(tasks)

    assert group.verification_commands == (GONE,)
    assert commands_failure(checkout, group.verification_commands) is None
