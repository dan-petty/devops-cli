"""The format run (#2789): the job formats the changed Python files before the other exit checks,
so a step with correct code that is not formatted ends done.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`. The formatter is a fake process that rewrites the files it gets, as `ruff format`
does; every other program is answered by `process_fake`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.roadmap.implement_step import (
    StepOutcome,
    StepStatus,
    build_step_inputs,
    run_step,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS,
    TEST_BODY,
    WINDOW,
    command_text,
    git,
    git_for_real,
    is_clean_at,
    make_checkout,
    programs_run,
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

FORMAT = "uv run ruff format --"
CHANGED_FILES = "src/sample.py tests/test_sample.py"
# The gate type-checks `src` only (#3090), so `mypy` gets the source file and not the test file.
SOURCE_FILES = "src/sample.py"
UNFORMATTED = SHOUT_CODE.replace('text.upper() + "!"', 'text.upper()+"!"')
LINE = "Formatted: src/sample.py"


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


def _format(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `ruff format` does to the files it gets: it puts a space round the `+`. With
    `--check` it writes nothing and exits 1 when a file would change."""
    check = "--check" in call.argv
    names = [
        word for word in call.argv[call.argv.index("format") + 1 :] if word not in {"--check", "--"}
    ]
    changed = 0
    for name in names:
        path = (call.cwd or Path()) / name
        before = path.read_text(encoding="utf-8")
        after = before.replace('upper()+"!"', 'upper() + "!"')
        changed += before != after
        if not check:
            path.write_text(after, encoding="utf-8")
    return subprocess.CompletedProcess(
        call.argv, int(check and changed > 0), f"{changed} file reformatted\n", ""
    )


def _formats(programs: ProcessFake) -> None:
    programs.answer(
        lambda call: command_text(call).startswith(FORMAT), ProcessAnswer(side_effect=_format)
    )


def _unformatted_group() -> tuple[tuple[str, dict[str, object]], ...]:
    calls = the_whole_group()
    return tuple(
        write_call("src/sample.py", UNFORMATTED) if call[1]["path"] == "src/sample.py" else call
        for call in calls
    )


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _formatted_script() -> ModelScript:
    return ModelScript(tool_calls(*_unformatted_group()), say("Done."))


def test_correct_code_that_is_unformatted_ends_done_with_the_formatted_file_in_the_commit(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _formats(programs)

    outcome = _step(store, checkout, _formatted_script())

    assert (
        outcome.status,
        outcome.reason,
        git(checkout, "show", "HEAD:src/sample.py") + "\n" == SHOUT_CODE,
        git(checkout, "status", "--porcelain"),
        [line for line in capsys.readouterr().err.splitlines() if "Formatted" in line],
    ) == (StepStatus.DONE, "", True, "", [LINE])


def test_code_that_the_formatter_leaves_as_it_is_prints_no_line(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, "Formatted" in capsys.readouterr().err) == (StepStatus.DONE, False)


def test_the_format_run_is_the_first_command_and_the_check_of_the_format_is_gone(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    uv = [command_text(call) for call in programs.calls if call.argv[0] == "uv"]
    assert uv == [
        f"{FORMAT} {CHANGED_FILES}",
        "uv run devops ci test tests/test_sample.py",
        "uv run devops docs check",
        f"uv run ruff check -- {CHANGED_FILES}",
        f"uv run mypy --python-version 3.14 --strict -- {SOURCE_FILES}",
        "uv run pre-commit run --hook-stage pre-commit",
    ]


def test_the_formatter_gets_the_changed_python_files_and_no_other_file(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    (checkout / "src" / "untouched.py").write_text("x = {  'a':1 }\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "Add a file the agent leaves alone")
    script = ModelScript(
        tool_calls(*the_whole_group(), write_call("docs/SAMPLE.md", "Notes.\n")), say("Done.")
    )

    _step(store, checkout, script)

    assert programs_run(programs, "uv")[0] == f"{FORMAT} {CHANGED_FILES}"


def test_a_lint_error_after_the_format_run_still_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    _formats(programs)
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(returncode=1, stdout="F401 unused import\n"),
    )

    outcome = _step(store, checkout, _formatted_script())

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        f"uv run ruff check -- {CHANGED_FILES} exited with status 1.\nF401 unused import",
        True,
    )


def test_a_type_error_after_the_format_run_still_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _formats(programs)
    programs.answer(
        lambda call: command_text(call).startswith("uv run mypy"),
        ProcessAnswer(returncode=1, stdout="error: bad type\n"),
    )

    outcome = _step(store, checkout, _formatted_script())

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        f"uv run mypy --python-version 3.14 --strict -- {SOURCE_FILES} exited with status 1.\n"
        "error: bad type",
    )


def test_a_file_with_a_syntax_error_stops_the_step_with_the_error_of_the_formatter(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    error = "error: Failed to parse src/sample.py:1:7: Expected a parameter"
    programs.answer(
        lambda call: command_text(call).startswith(FORMAT),
        ProcessAnswer(returncode=2, stderr=f"{error}\n"),
    )

    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        f"{FORMAT} {CHANGED_FILES} exited with status 2.\n{error}",
        True,
    )
    assert programs_run(programs, "uv") == [f"{FORMAT} {CHANGED_FILES}"]


def test_a_format_run_that_runs_out_of_time_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call).startswith(FORMAT),
        ProcessAnswer(side_effect=subprocess.TimeoutExpired("uv", 1)),
    )

    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert outcome.reason.startswith(f"{FORMAT} {CHANGED_FILES} ran out of time after ")


def test_a_step_with_no_python_file_runs_no_formatter(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(write_call("docs/SAMPLE.md", "Notes.\n"), write_call("tests/x.txt", TEST_BODY)),
        say("Done."),
    )

    _step(store, checkout, script)

    assert not [line for line in programs_run(programs, "uv") if "ruff" in line]


def test_a_file_named_like_an_option_is_a_path_for_each_tool(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    name = "--config=exclude.py"
    named = TASKS.replace(
        "Add `shout` to `src/sample.py`", f"Add `shout` to `src/sample.py` and `{name}`"
    )
    checkout = make_checkout(tmp_path / "named", named)
    script = ModelScript(tool_calls(*the_whole_group(), write_call(name, "x = 1\n")), say("Done."))

    outcome = _step(store, checkout, script)

    tools = [("ruff", "format"), ("ruff", "check")]
    commands = [line.split() for line in programs_run(programs, "uv") if "ruff" in line]
    assert (outcome.status, [(words[2:4], words[4:6]) for words in commands]) == (
        StepStatus.DONE,
        [(list(tool), ["--", name]) for tool in tools],
    )
    assert not [line for line in programs_run(programs, "uv") if name in line and "mypy" in line]


def _link_then_git(outside: Path) -> Callable[[ProcessCall], subprocess.CompletedProcess[str]]:
    """What the agent leaves behind: `src/link.py`, a link to a file outside the checkout, as the
    allowed `git` or `uv run python` could make it. It exists when the step stages the checkout."""

    def make(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        link = (call.cwd or Path()) / "src" / "link.py"
        if not link.is_symlink():
            link.symlink_to(outside)
        return git_for_real(call)

    return make


def test_a_link_named_like_a_python_file_stops_the_step_and_the_formatter_never_follows_it(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, tmp_path: Path
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    outside = tmp_path / "outside.py"
    outside.write_text(UNFORMATTED, encoding="utf-8")
    _formats(programs)
    programs.answer(
        lambda call: call.argv[:3] == ("git", "add", "-A"),
        ProcessAnswer(side_effect=_link_then_git(outside)),
    )
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outside.read_text(encoding="utf-8")) == (
        StepStatus.STOPPED,
        "The agent made a symbolic link: src/link.py. The step does not format a link.",
        UNFORMATTED,
    )
    assert is_clean_at(checkout, head)
    assert not [line for line in programs_run(programs, "uv") if "ruff" in line]


def test_the_instructions_say_that_the_job_formats_the_changed_python_files(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert "The job formats the changed Python files" in inputs.instructions
