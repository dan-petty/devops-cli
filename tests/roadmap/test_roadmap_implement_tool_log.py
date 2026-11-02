"""The log line of each tool call of an implement step (#2758).

The model is a pydantic-ai `FunctionModel` that a script answers, so no test reaches a model. The
line goes to the standard error stream, which `capsys` reads.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, ToolFailed

from devops_cli.config import constants
from devops_cli.roadmap.implement_shell_policy import IMPLEMENT_SHELL_REPLACEMENTS
from devops_cli.roadmap.implement_step import StepOutcome, run_step
from devops_cli.roadmap.implement_tool_log import ToolCallLog
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import TEST_BODY, WINDOW, write_call
from tests.support.model_script import ModelScript, say, tool_call, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
# Bare words of at most 24 characters that the mask of secrets changes.
SHORT_TOKEN = "ghp_" + "abcdefghijklmnopqrst"
AWS_KEY_ID = "AKIA" + "IOSFODNN7EXAMPLE"
# Bare words of at most 24 characters that the mask of secrets leaves as they are, such as a
# password or the header of a token that the model read from a file.
PASSWORD = "hunter2password"
JWT_HEADER = "eyJhbGciOiJIUzI1NiJ9"
# A secret that the mask of secrets cannot find, as it has no form.
PLAIN_SECRET = "hunter2-Sup3rS3cretPassw0rd"


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _lines(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return capsys.readouterr().err.splitlines()


def test_a_refused_program_is_logged_by_name_with_its_first_arguments(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(
        tool_call("shell", command="pytest tests/test_sample.py --flag=sentinel-value"),
        say("Done."),
    )

    _step(store, checkout, script)

    assert _lines(capsys) == [
        "Tool call: shell, started: pytest tests/test_sample.py --flag=<masked>",
        "Tool call: shell, program pytest, refused.",
    ]


def _call_lines(command: str, capsys: pytest.CaptureFixture[str]) -> list[str]:
    """The lines of one call of a tool that has a `command` argument and takes any command."""

    def shell(command: str) -> str:
        return "the output"

    Agent(
        ModelScript(tool_call("shell", command=command), say("Done.")).model(),
        tools=[shell],
        capabilities=[ToolCallLog().hooks()],
    ).run_sync("go")
    return _lines(capsys)


def _program_line(command: str, capsys: pytest.CaptureFixture[str]) -> str:
    """The line of the outcome of one call. The line before the call is `_call_lines()[0]`."""
    return _call_lines(command, capsys)[-1]


@pytest.mark.parametrize("program", ["git", "uv", "ruff", "mypy", "openspec", "devops"])
def test_a_program_of_the_allowlist_is_logged_by_name(
    capsys: pytest.CaptureFixture[str], program: str
) -> None:
    assert _program_line(f"{program} --flag=x 'a b'", capsys) == (
        f"Tool call: shell, program {program}, ok."
    )


@pytest.mark.parametrize(
    "command",
    [
        "API_KEY=hunter2 uv run x",
        "PASSWORD=hunter2 git status",
        f"{TOKEN} run",
        "/home/user/secret-dir/tool run",
        "\x1b[31mred git",
        "'unclosed quote",
        "'git status'",
        "''",
        "py=thon",
        "../tool run",
        "1python",
        "a" * 25,
        "ü" + "b",
        AWS_KEY_ID,
        SHORT_TOKEN,
        PASSWORD,
        JWT_HEADER,
        "a" * 24,
        "curl",
        "p0",
        "my-tool",
        "PYTHON",
    ],
)
def test_a_first_word_that_is_no_known_program_is_logged_as_other(
    capsys: pytest.CaptureFixture[str], command: str
) -> None:
    assert _program_line(command, capsys) == "Tool call: shell, program other, ok."


@pytest.mark.parametrize("word", sorted(IMPLEMENT_SHELL_REPLACEMENTS))
def test_a_program_of_the_table_of_replacements_is_logged_by_name(
    capsys: pytest.CaptureFixture[str], word: str
) -> None:
    assert _program_line(f"{word} --flag 'a b'", capsys) == f"Tool call: shell, program {word}, ok."


@pytest.mark.parametrize("command", ["", "   "])
def test_a_command_with_no_program_is_logged_with_no_program(
    capsys: pytest.CaptureFixture[str], command: str
) -> None:
    assert _program_line(command, capsys) == "Tool call: shell, ok."


def test_a_secret_as_the_first_word_never_reaches_the_log_of_a_step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_call("shell", command="API_KEY=hunter2 uv run x"), say("Done."))

    _step(store, checkout, script)

    assert _lines(capsys) == [
        "Tool call: shell, started: other",
        "Tool call: shell, program other, refused.",
    ]


def test_a_call_that_returns_is_logged_with_neither_its_path_nor_its_content(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(
        tool_calls(write_call("tests/test_sample.py", TEST_BODY + "# sentinel-content\n")),
        say("Done."),
    )

    _step(store, checkout, script)

    assert _lines(capsys) == ["Tool call: write_file, ok."]


def test_a_call_that_fails_validation_is_logged_as_a_retry_with_no_program(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_call("read_file"), say("Done."))

    _step(store, checkout, script)

    assert _lines(capsys) == ["Tool call: read_file, retry."]


def test_a_refused_path_is_a_retry_and_not_a_refused_command(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The file tools raise `PermissionError` for a path outside the root. That is no refused
    shell command, so it counts as another retry and its line has no program."""
    script = ModelScript(tool_call("read_file", path="/etc/passwd"), say("Done."))

    _step(store, checkout, script)

    err = capsys.readouterr().err
    assert err.splitlines() == ["Tool call: read_file, retry."]
    assert "passwd" not in err


def test_every_outcome_of_a_tool_call_has_its_line_and_its_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fine() -> str:
        return "the output"

    def forbidden(command: str) -> str:
        raise ModelRetry("not here") from PermissionError("not here")

    def outside(path: str) -> str:
        raise ModelRetry("not here") from PermissionError("not here")

    def again() -> str:
        raise ModelRetry("try again")

    def broken() -> str:
        raise ToolFailed("the workspace is read-only")

    script = ModelScript(
        tool_calls(
            ("fine", {}),
            ("forbidden", {"command": "cat"}),
            ("outside", {"path": "/y"}),
            ("again", {}),
            ("broken", {}),
        ),
        say("Done."),
    )
    log = ToolCallLog()
    agent = Agent(
        script.model(), tools=[fine, forbidden, outside, again, broken], capabilities=[log.hooks()]
    )

    agent.run_sync("go")

    assert (sorted(_lines(capsys)), log.refused, log.retried) == (
        [
            "Tool call: again, retry (try again).",
            "Tool call: broken, failed.",
            "Tool call: fine, ok.",
            "Tool call: forbidden, program cat, refused.",
            "Tool call: forbidden, started: cat",
            "Tool call: outside, retry.",
        ],
        Counter(cat=1),
        2,
    )


@pytest.mark.parametrize(
    ("command", "shown"),
    [
        pytest.param("git status", "git status", id="short"),
        pytest.param(
            "uv run devops ci test tests/test_a.py",
            "uv run devops ci test tests/test_a.py",
            id="six-words",
        ),
        pytest.param("uv run pytest -n 48 'tests/a b.py'", "uv run pytest -n 48 <masked>", id="q"),
        pytest.param("uv run pytest --numprocesses=48", "uv run pytest --numprocesses=48", id="n"),
        pytest.param(
            "git log --oneline -n 5 -- src tests docs", "git log --oneline -n 5 -- ...", id="words"
        ),
        pytest.param("git log " + "a" * 500, "git log " + "a" * 152 + " ...", id="chars"),
        pytest.param("API_KEY=hunter2 uv run x", "other", id="assignment"),
        pytest.param(PASSWORD, "other", id="password"),
        pytest.param("'unclosed quote", "other", id="unclosed"),
    ],
)
def test_the_command_of_a_call_is_logged_before_the_call_with_its_first_arguments(
    capsys: pytest.CaptureFixture[str], command: str, shown: str
) -> None:
    assert _call_lines(command, capsys)[0] == f"Tool call: shell, started: {shown}"


@pytest.mark.parametrize("command", ["", "   "])
def test_a_command_with_no_word_has_no_line_before_the_call(
    capsys: pytest.CaptureFixture[str], command: str
) -> None:
    assert _call_lines(command, capsys) == ["Tool call: shell, ok."]


def test_the_line_of_a_command_is_written_before_the_call_runs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A call that the kernel kills never ends, so only a line written before it names the
    cause (#2806)."""
    seen: list[list[str]] = []

    def shell(command: str) -> str:
        seen.append(_lines(capsys))
        return "the output"

    Agent(
        ModelScript(tool_call("shell", command="uv run pytest -n 48"), say("Done.")).model(),
        tools=[shell],
        capabilities=[ToolCallLog().hooks()],
    ).run_sync("go")

    assert seen == [["Tool call: shell, started: uv run pytest -n 48"]]


def test_a_secret_in_an_argument_never_reaches_the_line_of_a_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = _call_lines(f"git remote add origin https://user:{TOKEN}@example.com/x.git", capsys)

    assert [line for line in lines if TOKEN[:12] in line or TOKEN[-12:] in line] == []
    assert lines[0].startswith("Tool call: shell, started: git remote add origin ")


def test_an_escape_sequence_in_an_argument_stays_on_one_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = _call_lines("git log one\x1b[31mred\x07", capsys)

    assert lines == [
        "Tool call: shell, started: git log one\\x1b[31mred\\x07",
        "Tool call: shell, program git, ok.",
    ]


def test_a_line_break_in_an_argument_is_hidden_with_the_text_around_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = _call_lines("git commit -m 'one\ntwo'", capsys)

    assert lines[0] == "Tool call: shell, started: git commit -m <masked>"


@pytest.mark.parametrize(
    ("command", "shown"),
    [
        pytest.param(
            "git -c http.extraheader='AUTHORIZATION: basic dXNlcjpwYXNzd29yZDEyMw==' fetch",
            "git -c http.extraheader=<masked> fetch",
            id="header",
        ),
        pytest.param(
            "uv run devops config set ai.api_key=supersecretvalue123",
            "uv run devops config set ai.api_key=<masked>",
            id="dotted-key",
        ),
        pytest.param(
            "uv run devops x SECRET=abcdef1234567890abcdef",
            "uv run devops x SECRET=<masked>",
            id="upper-key",
        ),
        pytest.param(
            "uv run devops x password=hunter2", "uv run devops x password=<masked>", id="p"
        ),
        pytest.param(
            "git commit -m 'the password is hunter2'", "git commit -m <masked>", id="text"
        ),
        pytest.param(
            "uv run devops --api-key=abc123def456ghi789jkl012",
            "uv run devops --api-key=<masked>",
            id="hyphen",
        ),
        pytest.param(
            "uv run devops --password hunter2", "uv run devops --password <masked>", id="flag"
        ),
    ],
)
def test_an_argument_with_a_value_after_a_name_shows_its_name_and_not_its_value(
    capsys: pytest.CaptureFixture[str], command: str, shown: str
) -> None:
    """The mask of secrets finds a secret by its form, and a secret has no form in an argument
    such as `name=value`. The line keeps the name and hides the value, except for a number (#2806)."""
    assert _call_lines(command, capsys)[0] == f"Tool call: shell, started: {shown}"


# ── The reason of a retry (#2866) ─────────────────────────────────────────────────────────

MISSING = "old_text not found in src/other.py. No changes were written."


def _retry_lines(
    reason: str,
    capsys: pytest.CaptureFixture[str],
    *,
    path: str | None = None,
    root: Path | None = None,
) -> list[str]:
    """The lines of one call of a tool that retries with `reason`, and then a good call. `root` is
    the checkout that the log checks the `path` argument against."""
    calls = {"count": 0}

    def edit(path: str = "") -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ModelRetry(reason)
        return "done"

    args = {} if path is None else {"path": path}
    Agent(
        ModelScript(tool_call("edit", **args), tool_call("edit", **args), say("Done.")).model(),
        tools=[edit],
        capabilities=[ToolCallLog(root).hooks()],
    ).run_sync("go")
    return _lines(capsys)


def test_an_edit_whose_old_text_is_missing_logs_the_reason_that_the_tool_returned(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real `edit_file` of the harness refuses the edit. The line names the cause and holds
    no part of the text that the model looked for."""
    script = ModelScript(
        tool_call(
            "edit_file", path="src/other.py", old_text="SENTINEL-OLD-TEXT", new_text="OTHER = 2"
        ),
        say("Done."),
    )

    _step(store, checkout, script)

    assert _lines(capsys) == [f"Tool call: edit_file, retry ({MISSING})."]


def test_an_edit_that_matches_twice_logs_that_reason(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(
        tool_call("edit_file", path="src/sample.py", old_text="name", new_text="who"),
        say("Done."),
    )

    _step(store, checkout, script)

    assert _lines(capsys) == [
        "Tool call: edit_file, retry (old_text found 3 times in src/sample.py. Include more "
        "surrounding context to make the match unique. No changes were written.)."
    ]


def test_a_reason_without_the_path_gets_the_path_of_the_call(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_call("edit_file", path="src/other.py"), say("Done."))

    _step(store, checkout, script)

    assert _lines(capsys) == [
        "Tool call: edit_file, retry (Provide old_text and new_text, or a non-empty replacements "
        "list. Path: src/other.py)."
    ]


def test_a_reason_that_has_the_path_gets_no_second_path(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _retry_lines(MISSING, capsys, path="src/other.py", root=checkout)[0] == (
        f"Tool call: edit, retry ({MISSING})."
    )


def test_a_secret_in_a_reason_never_reaches_the_log(capsys: pytest.CaptureFixture[str]) -> None:
    lines = _retry_lines(f"File not found: src/{TOKEN}.py", capsys)

    assert [line for line in lines if TOKEN[:12] in line or TOKEN[-12:] in line] == []
    assert lines[0].startswith("Tool call: edit, retry (File not found: src/")


def test_a_secret_in_the_path_of_a_call_never_reaches_the_log(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = _retry_lines("Not here.", capsys, path=f"src/{TOKEN}.py", root=checkout)

    assert [line for line in lines if TOKEN[:12] in line or TOKEN[-12:] in line] == []
    assert lines[0] == "Tool call: edit, retry (Not here.)."


def test_a_plain_secret_as_the_path_of_a_call_is_hidden_in_the_reason(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The mask of secrets finds a secret by its form, and a password has none. The path of the
    call is text that the model chose, so the line shows it only when it names a file of the
    checkout."""
    lines = _retry_lines(
        f"File not found: {PLAIN_SECRET}", capsys, path=PLAIN_SECRET, root=checkout
    )

    assert lines[0] == "Tool call: edit, retry (File not found: <path>)."
    assert [line for line in lines if PLAIN_SECRET in line] == []


def test_a_plain_secret_as_the_path_gets_no_path_after_a_reason_that_lacks_it(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = _retry_lines("Not here.", capsys, path=PLAIN_SECRET, root=checkout)

    assert lines[0] == "Tool call: edit, retry (Not here.)."


def test_a_path_that_is_no_file_of_the_checkout_is_hidden_wherever_it_is_named(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file outside the root, and a path with a null byte, are no file of the checkout."""
    outside = checkout.parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    shown = [
        _retry_lines(f"Missing {path} and {path}.", capsys, path=path, root=checkout)[0]
        for path in ("../outside.txt", str(outside), "src/a\0b.py")
    ]

    assert shown == ["Tool call: edit, retry (Missing <path> and <path>.)."] * 3


def test_a_log_with_no_root_knows_no_path(capsys: pytest.CaptureFixture[str]) -> None:
    lines = _retry_lines("File not found: src/other.py", capsys, path="src/other.py")

    assert lines[0] == "Tool call: edit, retry (File not found: <path>)."


def test_an_absolute_path_of_the_checkout_is_shown_relative_to_it(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = str(checkout / "src" / "other.py")

    lines = _retry_lines(f"File not found: {path}", capsys, path=path, root=checkout)

    assert lines[0] == "Tool call: edit, retry (File not found: src/other.py)."


def test_a_reason_without_the_path_gets_the_path_of_the_call_when_the_log_knows_it(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = _retry_lines("Not here.", capsys, path="src/other.py", root=checkout)

    assert lines[0] == "Tool call: edit, retry (Not here. Path: src/other.py)."


def test_a_long_reason_without_the_path_still_ends_with_the_path(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    limit = constants.CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS
    suffix = " Path: src/other.py"

    lines = _retry_lines("x" * (3 * limit), capsys, path="src/other.py", root=checkout)

    assert lines[0] == f"Tool call: edit, retry ({'x' * (limit - len(suffix))} ...{suffix})."


def test_a_reason_that_fits_with_the_path_is_not_cut(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    limit = constants.CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS
    suffix = " Path: src/other.py"
    reason = "x" * (limit - len(suffix))

    lines = _retry_lines(reason, capsys, path="src/other.py", root=checkout)

    assert lines[0] == f"Tool call: edit, retry ({reason}{suffix})."


def test_a_reason_is_cut_to_the_constant_length(capsys: pytest.CaptureFixture[str]) -> None:
    limit = constants.CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS

    lines = _retry_lines("x" * (3 * limit), capsys)

    assert lines[0] == f"Tool call: edit, retry ({'x' * limit} ...)."


def test_a_reason_of_exactly_the_limit_is_not_cut(capsys: pytest.CaptureFixture[str]) -> None:
    limit = constants.CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS

    assert _retry_lines("x" * limit, capsys)[0] == f"Tool call: edit, retry ({'x' * limit})."


def test_a_line_break_in_a_reason_stays_on_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    lines = _retry_lines("one\ntwo\x1b[31m", capsys)

    assert lines[0] == "Tool call: edit, retry (one\\ntwo\\x1b[31m)."


def test_a_refusal_by_policy_and_a_failed_validation_log_no_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def outside(path: str) -> str:
        raise ModelRetry("`/etc/passwd` is outside the project.") from PermissionError("no")

    def typed(count: int) -> str:
        return "the output"

    log = ToolCallLog()
    Agent(
        ModelScript(
            tool_calls(
                ("outside", {"path": "/etc/passwd"}), ("typed", {"count": "SENTINEL-INPUT"})
            ),
            say("Done."),
        ).model(),
        tools=[outside, typed],
        capabilities=[log.hooks()],
    ).run_sync("go")

    assert sorted(_lines(capsys)) == ["Tool call: outside, retry.", "Tool call: typed, retry."]
    assert log.retried == 2
