"""`devops roadmap implement` (#2664): the groups of a `tasks.md`, the inputs of a step, and the
run of one group in a checkout.

pydantic-ai's `FunctionModel` answers each model request from a script, so no test reaches a
model. Git runs on a temporary repository. The programs of the exit checks (`uv`, `ruff` and
`mypy`) are answered at the process edge by `process_fake`, and git passes through to the real
program.
"""

from __future__ import annotations

import contextlib
import sqlite3
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelContextWindowExceededError,
    ModelHTTPError,
    ModelRequestTimeout,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai_harness.shell import Shell

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_LOG_CHARS,
    CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS,
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement import implement_step
from devops_cli.roadmap.implement.implement_limits import StepBudget
from devops_cli.roadmap.implement.implement_shell_policy import (
    IMPLEMENT_ALLOWED_PROGRAMS,
    IMPLEMENT_SHELL_PROGRAMS,
)
from devops_cli.roadmap.implement.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    build_agent,
    build_step_inputs,
    run_fix_step,
    run_step,
    shell_environment,
)
from devops_cli.roadmap.implement.implement_tool_log import ToolCallLog, logged_program
from devops_cli.roadmap.step_files import parse_task_groups
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    CHECK,
    DOCS,
    SHOUT_CODE,
    TASKS,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    git,
    git_for_real,
    is_clean_at,
    make_checkout,
    programs_run,
    rounds_spent,
    the_whole_group,
    write_call,
)
from tests.support.model_script import InStream, ModelScript, say, tool_call, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


# ── The groups of a tasks.md ──────────────────────────────────────────────────────────────


def test_a_tasks_file_holds_numbered_groups_with_their_tasks_commands_and_files() -> None:
    groups = parse_task_groups(TASKS)

    assert [
        (
            group.number,
            group.title,
            [(task.text, task.ticked) for task in group.tasks],
            group.verification_commands,
            group.named_paths,
        )
        for group in groups
    ] == [
        (
            1,
            "The first group",
            [
                ("[ ] Add the failing test `tests/test_sample.py` for `src/sample.py`", False),
                ("[ ] Add `shout` to `src/sample.py`", False),
            ],
            (
                "uv run devops ci test tests/test_sample.py",
                "uv run devops docs check",
            ),
            ("tests/test_sample.py", "src/sample.py", "shout"),
        ),
        (
            2,
            "The second group",
            [("[x] Document the function in `docs/SAMPLE.md`", True)],
            ("uv run devops docs check",),
            ("docs/SAMPLE.md",),
        ),
    ]


def test_the_text_of_a_group_runs_from_its_heading_to_the_next_heading() -> None:
    first, second = parse_task_groups(TASKS)

    assert (
        first.text.splitlines()[0],
        first.text.splitlines()[-1],
        second.text.splitlines()[0],
    ) == (
        "## 1. The first group",
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` and `$ uv run devops docs check`",
        "## 2. The second group",
    )


def test_a_section_without_a_number_is_no_group() -> None:
    groups = parse_task_groups("# Tasks\n\n## Workflow follow-up\n\n- [ ] Not a task of a group\n")

    assert groups == []


# ── The inputs of a step ──────────────────────────────────────────────────────────────────


def test_the_inputs_hold_the_item_the_change_the_group_and_the_files_it_names(
    store: InMemoryRoadmapStore, checkout: Path, snapshot: object
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert inputs.message == snapshot


def test_the_inputs_hold_no_file_that_the_group_does_not_name(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert ("OTHER = 1" in inputs.message, "The sample." in inputs.message) == (False, False)


def test_inputs_over_the_window_are_refused_with_the_measure_and_the_limit(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    measured = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW).tokens
    window = CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS + 50

    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=1, source=checkout, window=window)

    assert (refused.value.message, refused.value.exit_code, refused.value.error_code) == (
        f"The inputs of the step measure {measured} tokens. The limit is 50 tokens: the window "
        f"of {window} tokens minus {CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS} tokens for the "
        "turns of the run.",
        1,
        "ROADMAP_IMPLEMENT_REFUSED",
    )
    assert measured > 50


def test_a_checkout_with_no_change_folder_is_refused(
    store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    (empty / "openspec" / "changes").mkdir(parents=True)

    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=1, source=empty, window=WINDOW)

    assert refused.value.message == "The checkout has no change folder that matches 1-*."


def test_a_checkout_with_two_change_folders_for_the_item_is_refused(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    (checkout / "openspec" / "changes" / "1-other-change").mkdir()

    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert refused.value.message == (
        "The checkout has more than one change folder that matches 1-*: "
        "1-other-change, 1-sample-change."
    )


def test_a_group_that_the_change_lacks_is_refused(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=9, source=checkout, window=WINDOW)

    assert (
        refused.value.message == "The change 1-sample-change has no group 9. Its groups are 1, 2."
    )


def test_an_issue_that_is_no_item_is_refused(store: InMemoryRoadmapStore, checkout: Path) -> None:
    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=5, group=1, source=checkout, window=WINDOW)

    assert refused.value.message == "#5 is not an item of the roadmap."


# ── The run of a step ─────────────────────────────────────────────────────────────────────


def _step(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript, group: int = 1
) -> StepOutcome:
    return run_step(
        store, item=1, group=group, source=checkout, model=script.model(), window=WINDOW
    )


def test_a_group_that_the_agent_completes_ends_done_with_one_commit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    before = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_calls(*the_whole_group()),
        say("The group is done."),
    )

    outcome = _step(store, checkout, script)

    head = git(checkout, "rev-parse", "HEAD")
    assert (
        outcome.status,
        outcome.reason,
        outcome.commit,
        outcome.last_message,
        outcome.requests,
        git(checkout, "rev-parse", "HEAD~1"),
        git(checkout, "log", "-1", "--format=%s"),
        sorted(git(checkout, "show", "--name-only", "--format=", "HEAD").splitlines()),
        git(checkout, "status", "--porcelain"),
    ) == (
        StepStatus.DONE,
        "",
        head,
        "The group is done.",
        2,
        before,
        "chore: The first group (#1)",
        [TASKS_PATH, "src/sample.py", "tests/test_sample.py"],
        "",
    )


def test_the_outcome_counts_the_tool_calls_of_all_replies(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    test_call, code_call, tick_call = the_whole_group()
    script = ModelScript(tool_calls(test_call, code_call), tool_calls(tick_call), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.requests, outcome.tool_calls) == (StepStatus.DONE, 3, 3)


def test_the_exit_checks_format_first_run_each_command_once_then_the_static_checks_on_the_changed_files(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    py = "src/sample.py tests/test_sample.py"
    uv = [call for call in programs.calls if call.argv[0] == "uv"]
    commands = [command_text(call) for call in uv]
    first_exit_check = commands.index(f"uv run ruff format -- {py}")
    # The tick of the agent runs the verification of each task before the exit checks (#3054).
    assert commands[:first_exit_check] == [
        "uv run devops ci test tests/test_sample.py",
        "uv run devops ci test tests/test_sample.py",
        "uv run devops docs check",
    ]
    assert (commands[first_exit_check:], {call.cwd for call in uv}) == (
        [
            f"uv run ruff format -- {py}",
            "uv run devops ci test tests/test_sample.py",
            "uv run devops docs check",
            f"uv run ruff check -- {py}",
            "uv run mypy --python-version 3.14 --strict -- src/sample.py",
        ],
        {checkout},
    )


def test_a_failed_verification_command_stops_the_step_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    programs.answer(
        lambda call: command_text(call) == CHECK, ProcessAnswer(returncode=1, stdout="no docs\n")
    )
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        outcome.commit,
        is_clean_at(checkout, head),
        (checkout / "tests" / "test_sample.py").exists(),
        "def shout" in (checkout / "src" / "sample.py").read_text(encoding="utf-8"),
    ) == (
        StepStatus.STOPPED,
        f"{CHECK} exited with status 1.\nno docs",
        "",
        True,
        False,
        False,
    )


def _is_clean_at_wip(checkout: Path, start: str) -> bool:
    """Whether the checkout is clean, one `wip:` commit past `start`."""
    return (
        git(checkout, "rev-list", "--count", f"{start}..HEAD") == "1"
        and git(checkout, "log", "-1", "--format=%s").startswith("wip:")
        and git(checkout, "status", "--porcelain") == ""
    )


def test_a_failed_static_check_stops_the_step_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(returncode=1, stdout="E501 too long\n"),
    )

    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    # Every task passed its verification, so the checkout goes back to the `wip:` commit (#3054).
    assert (outcome.status, outcome.reason, _is_clean_at_wip(checkout, head)) == (
        StepStatus.STOPPED,
        "uv run ruff check -- src/sample.py tests/test_sample.py exited with status 1.\nE501 too long"
        + rounds_spent(3),
        True,
    )


def test_a_text_change_to_another_group_is_undone_and_the_step_ends_done(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    other = TICKED.replace("Document the function", "Describe the function")
    script = ModelScript(tool_calls(write_call(TASKS_PATH, other)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n") == (
        StepStatus.DONE,
        "",
        TICKED,
    )


def test_a_task_that_the_agent_removes_is_restored_and_the_group_is_ticked(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    shorter = TICKED.replace(
        "- [x] Add `shout` to `src/sample.py`\n"
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` and `$ uv run devops docs check`\n",
        "",
    )
    script = ModelScript(
        tool_calls(write_call("src/sample.py", SHOUT_CODE), write_call(TASKS_PATH, shorter)),
        say("Done."),
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n") == (
        StepStatus.DONE,
        "",
        TICKED,
    )


def test_a_verification_command_that_is_no_command_line_does_not_run(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    tasks = TASKS.replace(DOCS, "uv run 'devops")
    checkout = make_checkout(tmp_path, tasks)
    ticked = tasks.replace("- [ ] Add", "- [x] Add")
    script = ModelScript(tool_calls(write_call(TASKS_PATH, ticked)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        "The verification command uv run 'devops is refused: it is not a valid command line.",
    )


def test_a_verification_command_outside_the_allowlist_does_not_run(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    tasks = TASKS.replace(DOCS, "curl http://example.com")
    checkout = make_checkout(tmp_path, tasks)
    ticked = tasks.replace("- [ ] Add", "- [x] Add")
    script = ModelScript(tool_calls(write_call(TASKS_PATH, ticked)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, programs_run(programs, "curl")) == (
        StepStatus.STOPPED,
        "The verification command curl http://example.com is refused: `curl` is not one of: "
        + ", ".join(IMPLEMENT_ALLOWED_PROGRAMS)
        + ".",
        [],
    )


def test_a_group_whose_tasks_are_ticked_and_that_changes_no_file_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _step(store, checkout, ModelScript(say("Nothing to do.")), group=2)

    assert (outcome.status, outcome.reason, outcome.last_message) == (
        StepStatus.STOPPED,
        "The agent changed no file.",
        "Nothing to do.",
    )


def test_a_commit_that_a_hook_refuses_stops_the_step_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    hook = checkout / ".git" / "hooks" / "commit-msg"
    hook.write_text(
        '#!/bin/sh\ngrep -q "^wip:" "$1" && exit 0\necho refused by the hook\nexit 1\n',
        encoding="utf-8",
    )
    hook.chmod(0o755)

    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.reason, _is_clean_at_wip(checkout, head)) == (
        StepStatus.STOPPED,
        "The commit failed.\nrefused by the hook",
        True,
    )


# What the refusal adds to the text of the shell (#2773).
ALLOWED_HINT = (
    "These programs are allowed: "
    + ", ".join(f"`{program}`" for program in IMPLEMENT_SHELL_PROGRAMS)
    + ". Run the commands of the project "
    "with `uv run`, for example `uv run devops ci test <file>`."
)
OPERATOR_HINT = (
    "Run one command in each call. Do not chain commands. "
    "Do not use `cd`: every command runs in the checkout."
)


def test_the_shell_tool_refuses_a_program_outside_the_allowlist_and_the_run_goes_on(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A refused command starts no process: the process floor fails a test that starts one."""
    script = ModelScript(
        tool_call("shell", command="curl http://example.com"),
        tool_call("shell", command="git status; curl http://example.com"),
        say("Done."),
    )

    outcome = _step(store, checkout, script)

    assert (outcome.last_message, outcome.requests, script.tool_answers()) == (
        "Done.",
        3,
        [
            f"Command 'curl' is not in the allowed list. {ALLOWED_HINT}",
            f"Shell operator ';' is not allowed. {OPERATOR_HINT}",
        ],
    )


def test_the_shell_tool_refuses_the_devops_cli_and_openspec(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The shell reaches no command that writes to GitHub: `devops gh` is not on its list."""
    script = ModelScript(
        tool_call("shell", command="devops gh api -X POST repos/example/roadmap/issues"),
        tool_call("shell", command="openspec archive 1-sample-change"),
        say("Done."),
    )

    _step(store, checkout, script)

    assert script.tool_answers() == [
        f"Command 'devops' is not in the allowed list. {ALLOWED_HINT}",
        f"Command 'openspec' is not in the allowed list. {ALLOWED_HINT}",
    ]


def test_the_shell_runs_with_a_scratch_home_and_the_cache_of_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No git configuration, helper or key of the user's home reaches a shell command."""
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    monkeypatch.delenv("UV_PYTHON", raising=False)
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)

    env = shell_environment(tmp_path / "home")

    assert env == {
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "home" / ".config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }


def test_the_shell_gets_the_interpreter_that_uv_is_told_to_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv run` in a step finds no interpreter in the runner image unless `UV_PYTHON` reaches it:
    the image forbids a Python download and its Python can be older than `.python-version`."""
    monkeypatch.setenv("UV_PYTHON", "/usr/local/bin/python3")

    env = shell_environment(tmp_path / "home")

    assert env["UV_PYTHON"] == "/usr/local/bin/python3"


def test_the_shell_gets_the_worker_bound_of_the_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`pytest-xdist` counts the CPUs of the node. The pod of the runner sets the bound, and the
    shell of a step gets no other variable of the job, so the bound must be passed on (#2806)."""
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "2")

    env = shell_environment(tmp_path / "home")

    assert env["PYTEST_XDIST_AUTO_NUM_WORKERS"] == "2"


def test_the_agent_of_a_step_runs_its_shell_in_that_environment(
    tmp_path: Path, checkout: Path
) -> None:
    log = ToolCallLog()
    agent = build_agent(
        ModelScript(say("x")).model(),
        checkout,
        "go",
        WINDOW,
        tmp_path / "home",
        log,
        StepBudget(progress=log.progress),
    )

    leaves: list[Any] = []

    def collect(leaf: Any) -> Any:
        leaves.append(leaf)
        return leaf

    agent.root_capability.visit_and_replace(collect)

    shells = [leaf for leaf in leaves if isinstance(leaf, Shell)]
    assert [shell.env for shell in shells] == [shell_environment(tmp_path / "home")]
    assert [shell.allowed_commands for shell in shells] == [list(IMPLEMENT_SHELL_PROGRAMS)]


def test_a_commit_that_the_agent_makes_is_reset_and_the_step_commits_the_work(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The shell allowlist admits git, so the agent can commit. Its effect is scripted here (#3575).
    The step moves HEAD back, keeps the work in the checkout and makes the only commit."""
    head = git(checkout, "rev-parse", "HEAD")

    def agent_commits() -> None:
        (checkout / "src" / "other.py").write_text("OTHER = 3\n", encoding="utf-8")
        git(checkout, "add", "-A")
        git(checkout, "commit", "-q", "-m", "own commit")

    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), effects={2: agent_commits})

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.DONE, "")
    assert git(checkout, "rev-parse", "HEAD") == outcome.commit
    assert git(checkout, "rev-parse", "HEAD~1") == head
    assert "own commit" not in git(checkout, "log", "--format=%s", f"{head}..HEAD")
    shown = git(checkout, "show", "--format=", "HEAD")
    assert ("+def shout(text: str) -> str:" in shown, "+OTHER = 3" in shown) == (True, True)


def test_the_step_prints_one_line_for_a_head_that_it_resets(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    moved: list[tuple[str, str]] = []

    def agent_commits() -> None:
        (checkout / "src" / "other.py").write_text("OTHER = 3\n", encoding="utf-8")
        before = git(checkout, "rev-parse", "HEAD")
        git(checkout, "add", "-A")
        git(checkout, "commit", "-q", "-m", "own commit")
        moved.append((before, git(checkout, "rev-parse", "HEAD")))

    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), effects={2: agent_commits})

    _step(store, checkout, script)

    notes = [line for line in capsys.readouterr().err.splitlines() if "moved HEAD" in line]
    assert notes == [
        f"The agent moved HEAD from {moved[0][0]} to {moved[0][1]}."
        f" The step reset HEAD to {moved[0][0]} and kept the changes."
    ]


def test_a_reset_head_does_not_hide_a_failed_check(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The checks judge the work after the reset, so a failed check stops the step and the
    checkout goes back to its start."""
    head = git(checkout, "rev-parse", "HEAD")

    def agent_commits() -> None:
        git(checkout, "add", "-A")
        git(checkout, "commit", "-q", "-m", "own commit")

    programs.answer(lambda call: command_text(call) == CHECK, ProcessAnswer(returncode=1))
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), effects={2: agent_commits})

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.commit, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "",
        True,
    )
    assert f"{CHECK} exited with status 1" in outcome.reason


def test_a_tasks_file_that_the_agent_removes_is_written_back_and_the_group_is_ticked(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(*the_whole_group()),
        say("Done."),
        effects={2: (checkout / TASKS_PATH).unlink},
    )

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        (checkout / TASKS_PATH).exists(),
        git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n",
    ) == (StepStatus.DONE, "", True, TICKED)


def test_a_tasks_file_with_bytes_that_are_not_text_is_written_back_and_the_group_is_ticked(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    def garble() -> None:
        (checkout / TASKS_PATH).write_bytes(b"\xff\xfe not utf-8")

    script = ModelScript(tool_calls(*WORK), say("Done."), effects={2: garble})

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, git(checkout, "show", f"HEAD:{TASKS_PATH}") + "\n") == (
        StepStatus.DONE,
        "",
        TICKED,
    )


def test_the_agent_has_the_file_tools_and_the_shell_and_no_delegate(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(say("Done."))

    _step(store, checkout, script)

    assert script.tools_offered[0] == [
        "edit_file",
        "grep",
        "list_files",
        "read_file",
        "shell",
        "write_file",
    ]


def test_the_first_request_holds_the_inputs_of_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(say("Done."))
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    _step(store, checkout, script)

    prompts = [part for message in script.seen[0] for part in message.parts]
    assert inputs.message in [str(getattr(part, "content", "")) for part in prompts]


def test_a_run_that_never_ends_stops_at_the_request_limit_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_call("write_file", path="tests/test_sample.py", content=TEST_BODY),
        tool_call("read_file", path="docs/SAMPLE.md"),
    )

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        outcome.requests,
        len(script.seen),
        is_clean_at(checkout, head),
    ) == (
        StepStatus.STOPPED,
        REQUEST_LIMIT_REASON,
        CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
        CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
        True,
    )


def test_a_run_that_calls_too_many_tools_stops_at_the_tool_call_limit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """Four calls in each reply, so that the tool call limit comes before the request limit."""
    head = git(checkout, "rev-parse", "HEAD")
    batch = 4
    script = ModelScript(tool_calls(*[("read_file", {"path": "docs/SAMPLE.md"})] * batch))

    outcome = _step(store, checkout, script)

    assert CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS // batch < CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS
    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        TOOL_CALL_LIMIT_REASON,
        True,
    )
    assert outcome.requests < CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS


def test_a_tool_result_is_cut_to_the_cap_of_a_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    (checkout / "docs" / "SAMPLE.md").write_text("x" * 60000 + "\n", encoding="utf-8")
    git(checkout, "commit", "-q", "-am", "a long file")
    script = ModelScript(tool_call("read_file", path="docs/SAMPLE.md"), say("Done."))

    _step(store, checkout, script, group=2)

    assert len(script.tool_answers()[0]) <= CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS


def test_a_checkout_with_uncommitted_changes_is_refused_before_any_request(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    (checkout / "notes.txt").write_text("mine\n", encoding="utf-8")
    script = ModelScript(say("Done."))

    with pytest.raises(RoadmapImplementError) as refused:
        _step(store, checkout, script)

    assert (refused.value.message, script.seen, (checkout / "notes.txt").exists()) == (
        f"The checkout {checkout} has uncommitted changes. A step resets the checkout when it "
        "fails. Commit or discard the changes first.",
        [],
        True,
    )


def test_a_refused_key_raises_after_the_checkout_is_reset(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_call("write_file", path="tests/test_sample.py", content=TEST_BODY),
        ModelHTTPError(401, "gateway", {"error": "bad key"}),
    )

    with pytest.raises(AICredentialsError) as raised:
        _step(store, checkout, script)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"

    assert is_clean_at(checkout, head)


def _spend_rows(ledger: SpendLedger) -> Sequence[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        rows: Sequence[tuple[Any, ...]] = conn.execute(
            "SELECT request_type, stage, prompt_tokens > 0, completion_tokens > 0 "
            "FROM ai_spend_records"
        ).fetchall()
    return rows


def test_the_spend_of_a_step_is_one_record_in_the_ledger(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, spend_ledger: SpendLedger
) -> None:
    script = ModelScript(tool_call("read_file", path="docs/SAMPLE.md"), say("Done."))

    outcome = _step(store, checkout, script)

    assert (_spend_rows(spend_ledger), outcome.requests, outcome.input_tokens > 0) == (
        [("agent_run", "implement", 1, 1)],
        2,
        True,
    )


# ── The turn for the missing ticks (#2721) ────────────────────────────────────────────────

WORK = (write_call("tests/test_sample.py", TEST_BODY), write_call("src/sample.py", SHOUT_CODE))
TICK = write_call(TASKS_PATH, TICKED)
FORGOT = "A forgetful agent writes the work and does not tick."


def _ruff_fails(programs: ProcessFake) -> None:
    """Every `ruff check` fails, so each exit check of the group gets a repair turn (#3488)."""
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(returncode=1, stdout="E501 too long\n"),
    )


def _ruff_fails_once(programs: ProcessFake) -> None:
    """The first `ruff check` fails and the later ones pass, so one repair turn fixes the check."""
    pending = [1]

    def lint(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        code = pending.pop() if pending else 0
        return subprocess.CompletedProcess(
            call.argv, code, stdout="E501 too long\n" if code else "", stderr=""
        )

    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=lint),
    )


def test_an_agent_that_forgot_the_ticks_ends_done_with_no_extra_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    before = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_calls(*WORK), say("The work is done."))

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        outcome.requests,
        git(checkout, "rev-parse", "HEAD~1"),
        sorted(git(checkout, "show", "--name-only", "--format=", "HEAD").splitlines()),
        git(checkout, "status", "--porcelain"),
    ) == (
        StepStatus.DONE,
        "",
        2,
        before,
        [TASKS_PATH, "src/sample.py", "tests/test_sample.py"],
        "",
    )


def test_a_failed_verification_command_stops_the_step_with_no_extra_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call) == DOCS, ProcessAnswer(returncode=1, stdout="no docs\n")
    )
    script = ModelScript(tool_calls(*WORK), say(FORGOT))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, len(script.seen)) == (
        StepStatus.STOPPED,
        f"{DOCS} exited with status 1.\nno docs",
        2,
    )


def test_a_failed_static_check_gets_one_extra_turn_for_it_and_none_for_the_ticks(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, config: Callable[..., Path]
) -> None:
    """The turn for the failure lists the unticked tasks too (#2795), so no turn for them follows."""
    config(roadmap={"implement": {"repair_rounds": 1}})
    programs.answer(
        lambda call: command_text(call).startswith("uv run mypy"),
        ProcessAnswer(returncode=1, stdout="error: bad type\n"),
    )
    script = ModelScript(tool_calls(*WORK), say(FORGOT))

    outcome = _step(store, checkout, script)

    assert (outcome.status, len(script.seen)) == (StepStatus.STOPPED, 3)
    assert outcome.reason.endswith("exited with status 1.\nerror: bad type" + rounds_spent(1))


def test_the_spend_of_both_turns_is_in_the_ledger_and_the_outcome(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, spend_ledger: SpendLedger
) -> None:
    _ruff_fails_once(programs)
    script = ModelScript(tool_calls(*WORK), say("Done."), tool_calls(TICK), say("Ticked."))

    outcome = _step(store, checkout, script)

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT stage, prompt_tokens, completion_tokens FROM ai_spend_records"
        ).fetchall()
    assert (
        [row[0] for row in rows],
        sum(row[1] for row in rows),
        sum(row[2] for row in rows),
        outcome.requests,
    ) == (["implement", "implement"], outcome.input_tokens, outcome.output_tokens, 4)


def test_a_fix_step_gets_no_extra_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(write_call("src/sample.py", SHOUT_CODE)), say("Fixed."))

    outcome = _fix(store, checkout, script)

    assert (outcome.status, len(script.seen)) == (StepStatus.DONE, 2)


def test_the_inputs_of_a_step_name_the_tasks_file_and_those_of_a_fix_step_do_not(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    step = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)
    fix = build_step_inputs(
        store,
        item=1,
        group=0,
        source=checkout,
        window=WINDOW,
        fix=FixRequest(check="Static Analysis", log="E501"),
    )

    assert (
        f"# The tasks file\n\n`{TASKS_PATH}`" in step.message,
        "# The tasks file" in fix.message,
    ) == (
        True,
        False,
    )


def test_the_instructions_say_that_the_job_ticks_every_task_of_a_passing_group(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert "The job ticks every task of your group when the exit checks of the group pass" in (
        inputs.instructions
    )
    assert "not done until every task of your group is ticked" not in inputs.instructions
    assert "`- [ ]` to `- [x]`" in inputs.instructions


def test_the_instructions_say_that_a_reply_has_a_cap_and_a_long_file_is_written_in_parts(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert "Each reply of yours has an output cap" in inputs.instructions
    assert (
        "stops and the work after your last kept task is lost"
        in inputs.instructions.split("output cap")[1]
    )
    assert "in parts with `edit_file`" in inputs.instructions


# ── The diff of a stopped step (#2721) ────────────────────────────────────────────────────

TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _stopped_on_a_check(programs: ProcessFake) -> None:
    """The first verification command fails, so no task passes it and the step keeps nothing:
    the diff holds all the work (#3054)."""
    programs.answer(
        lambda call: command_text(call) == CHECK, ProcessAnswer(returncode=1, stdout="no docs\n")
    )


def test_a_stopped_step_reports_the_diff_of_the_work_it_discarded(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    _stopped_on_a_check(programs)

    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.diff_cut, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        False,
        True,
    )
    assert "diff --git a/src/sample.py b/src/sample.py" in outcome.diff
    assert "+def shout(text: str) -> str:" in outcome.diff
    assert "diff --git a/tests/test_sample.py b/tests/test_sample.py" in outcome.diff
    assert "+def test_shout() -> None:" in outcome.diff
    assert "+- [x] Add `shout` to `src/sample.py`" in outcome.diff


def test_the_diff_of_a_stopped_step_holds_the_work_of_an_agent_that_committed(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    def agent_commits() -> None:
        git(checkout, "add", "-A")
        git(checkout, "commit", "-q", "-m", "own commit")

    programs.answer(lambda call: command_text(call) == CHECK, ProcessAnswer(returncode=1))
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), effects={2: agent_commits})

    outcome = _step(store, checkout, script)

    assert (outcome.status, "+def shout(text: str) -> str:" in outcome.diff) == (
        StepStatus.STOPPED,
        True,
    )


def test_the_diff_of_a_stopped_step_is_masked(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _stopped_on_a_check(programs)
    leaky = write_call("src/sample.py", SHOUT_CODE + f'\nTOKEN = "{TOKEN}"\n')

    outcome = _step(store, checkout, ModelScript(tool_calls(leaky, TICK), say("Done.")))

    assert (TOKEN in outcome.diff, "<masked-github-token>" in outcome.diff) == (False, True)


def test_the_diff_of_a_stopped_step_is_cut_to_a_constant_size(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _stopped_on_a_check(programs)
    long_file = write_call(
        "src/sample.py", "y" * 3 * constants.CONST_ROADMAP_IMPLEMENT_DIFF_CHARS + "\n"
    )

    outcome = _step(store, checkout, ModelScript(tool_calls(long_file, TICK), say("Done.")))

    assert (len(outcome.diff), outcome.diff_cut) == (
        constants.CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
        True,
    )


def test_the_diff_of_a_stopped_step_is_masked_before_it_is_cut(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A private key spans more lines than the cut keeps. A cut before the masking would leave
    its first lines and no end marker, and the masking would find no key to mask."""
    _stopped_on_a_check(programs)
    key = (
        "-----BEGIN "
        + "PRIVATE KEY-----\n"
        + ("A" * 64 + "\n") * 400
        + "-----END "
        + "PRIVATE KEY-----\n"
    )
    file = write_call(
        "src/sample.py", key + "y" * 3 * constants.CONST_ROADMAP_IMPLEMENT_DIFF_CHARS + "\n"
    )

    outcome = _step(store, checkout, ModelScript(tool_calls(file, TICK), say("Done.")))

    assert (len(outcome.diff), "PRIVATE KEY" in outcome.diff, "A" * 16 in outcome.diff) == (
        constants.CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
        False,
        False,
    )
    assert "<masked-private-key>" in outcome.diff


def test_a_stopped_step_reports_the_diff_of_a_file_that_is_not_utf8(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A Latin-1 file in the discarded work must not crash the job that reads its diff."""
    _stopped_on_a_check(programs)

    def agent_writes_latin1() -> None:
        (checkout / "tests" / "test_sample_latin1.py").write_bytes(
            "caf\xe9 au lait\n".encode("latin-1")
        )

    script = ModelScript(
        tool_calls(*the_whole_group()), say("Done."), effects={2: agent_writes_latin1}
    )

    outcome = _step(store, checkout, script)

    assert outcome.status is StepStatus.STOPPED
    assert "caf\ufffd au lait" in outcome.diff


def test_a_stopped_step_masks_only_a_bounded_part_of_a_very_large_diff(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The masking is slower than linear, so its input is cut before it runs. The cut keeps a
    multiple of the limit, so that a secret inside the shown part is still masked whole."""
    _stopped_on_a_check(programs)
    limit = constants.CONST_ROADMAP_IMPLEMENT_DIFF_CHARS
    masked_sizes: list[int] = []
    real_mask = implement_step.mask_secrets

    def spy(text: str) -> str:
        masked_sizes.append(len(text))
        return real_mask(text)

    monkeypatch.setattr(implement_step, "mask_secrets", spy)
    huge = write_call("src/sample.py", ("y" * 99 + "\n") * (50 * limit // 100))

    outcome = _step(store, checkout, ModelScript(tool_calls(huge, TICK), say("Done.")))

    assert (len(outcome.diff), outcome.diff_cut) == (limit, True)
    assert masked_sizes
    assert max(masked_sizes) <= constants.CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS


def test_a_done_step_reports_no_diff(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.diff, outcome.diff_cut) == (StepStatus.DONE, "", False)


def test_a_stopped_step_reads_its_diff_with_no_external_program_and_no_text_conversion(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A diff driver that the agent sets in `.git/config` would run in the job's process."""
    _stopped_on_a_check(programs)

    _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    diffs = [call.argv for call in programs.calls if call.argv[:2] == ("git", "diff")]
    reading = [argv for argv in diffs if "--no-ext-diff" in argv]
    assert reading
    assert all("--no-textconv" in argv for argv in reading)


# ── The reason of a stop (#2758) ──────────────────────────────────────────────────────────

LIMIT_ADVICE = (
    "Consider raising the limit, or see the docs on usage limits for budget-aware patterns: "
    "https://pydantic.dev/docs/ai/core-concepts/agent/#usage-limits"
)
REQUEST_LIMIT_REASON = (
    "UsageLimitExceeded: The next request would exceed the request_limit of "
    f"{CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS}. {LIMIT_ADVICE}"
)
TOOL_CALL_LIMIT_REASON = (
    "UsageLimitExceeded: The next tool call(s) would exceed the tool_calls_limit of "
    f"{CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS} "
    f"(tool_calls={CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS + 4}). {LIMIT_ADVICE}"
)
RETRY_LIMIT_MESSAGE = (
    "Tool 'shell' exceeded max retries count of 5. Consider raising the retry limit, or see the "
    "docs on tool retries: https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/#tool-retries"
)


REFUSAL_LIMIT_MESSAGE = (
    "Too many commands refused by policy in one step: the limit is "
    f"{CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS}."
)
BROKE = UnexpectedModelBehavior("The reply broke the rules.")


def test_a_model_that_keeps_calling_a_refused_program_stops_with_the_message_and_the_count(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The shell refuses `pytest`. The model asks for `pytest` in every reply, as the Job on #2656
    may have done: the shell refuses it up to the limit of refusals, and the next call ends the run
    (#3271)."""
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_call("shell", command="pytest tests/test_sample.py"))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.requests, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        f"UnexpectedModelBehavior: {REFUSAL_LIMIT_MESSAGE}\n"
        f"Refused commands: pytest {CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS + 1}. Other retries: 0.",
        CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS + 1,
        True,
    )


def test_the_reason_counts_the_refused_commands_by_program_from_the_most_refused(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        *(
            tool_call("shell", command=f"{program} x")
            for program in "cd python cd python python python".split()
        ),
        BROKE,
    )

    outcome = _step(store, checkout, script)

    assert outcome.reason.endswith("\nRefused commands: python 4, cd 2. Other retries: 0.")


def test_the_reason_joins_the_programs_beyond_the_limit_to_other(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """Five programs, one of them twice: the reason lists four, and the fifth joins `other`."""
    script = ModelScript(
        *(
            tool_call("shell", command=f"{name} x")
            for name in ("pytest", "rg", "pip", "cd", "python3", "python3")
        ),
        BROKE,
    )

    outcome = _step(store, checkout, script)

    assert constants.CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS == 4
    assert outcome.reason.endswith(
        "\nRefused commands: python3 2, pytest 1, rg 1, pip 1, other 1. Other retries: 0."
    )


def test_a_first_word_that_is_no_known_program_is_counted_as_other_and_never_shown(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_call("shell", command="API_KEY=hunter2 uv run x"), BROKE)

    outcome = _step(store, checkout, script)

    shown = logged_program("API_KEY=hunter2")
    assert outcome.reason.endswith(f"\nRefused commands: {shown} 1. Other retries: 0.")
    assert "hunter2" not in outcome.reason


def test_a_short_word_that_is_no_known_program_is_counted_as_other_and_never_shown(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A password that the model read from a file is a short bare word, and the mask of secrets
    leaves it as it is. The reason goes to a comment on GitHub, so it must not show the word."""
    script = ModelScript(tool_call("shell", command="hunter2password x"), BROKE)

    outcome = _step(store, checkout, script)

    shown = logged_program("hunter2password")
    assert outcome.reason.endswith(f"\nRefused commands: {shown} 1. Other retries: 0.")
    assert "hunter2password" not in outcome.reason


def test_a_model_that_sends_invalid_arguments_stops_with_the_count_of_other_retries(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_call("read_file"))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        f"UnexpectedModelBehavior: {RETRY_LIMIT_MESSAGE.replace('shell', 'read_file')}\n"
        "Refused commands: 0. Other retries: 6.",
    )


def test_a_model_that_asks_for_a_path_outside_the_root_counts_other_retries_not_refused_commands(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_call("read_file", path="/etc/passwd"))

    outcome = _step(store, checkout, script)

    assert outcome.reason.endswith("\nRefused commands: 0. Other retries: 6.")


MISSING_TEXT = "old_text not found in src/other.py. No changes were written."


def _edit_missing(path: str = "src/other.py") -> ModelResponse:
    return tool_call("edit_file", path=path, old_text="SENTINEL-OLD-TEXT", new_text="x")


def test_a_tool_that_ends_the_run_on_retries_names_its_last_reasons(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The reasons are the messages of the `ModelRetry` of the harness tool (#2866). The reason of
    the run keeps the last three of them, and not the old text that the model looked for."""
    script = ModelScript(
        *(_edit_missing(f"src/other{number}.py") for number in range(5)), _edit_missing()
    )

    outcome = _step(store, checkout, script)

    assert outcome.reason.endswith(
        "\nRefused commands: 0. Other retries: 6.\nLast retries of edit_file: "
        "File not found: <path> | File not found: <path> | "
        f"{MISSING_TEXT}"
    )
    assert "SENTINEL-OLD-TEXT" not in outcome.reason


def test_the_last_reasons_of_a_run_hold_no_secret(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(_edit_missing(f"src/{TOKEN}.py"))

    outcome = _step(store, checkout, script)

    assert "Last retries of edit_file: File not found: <path>" in outcome.reason
    assert TOKEN[:12] not in outcome.reason
    assert TOKEN[-12:] not in outcome.reason


def test_the_last_reasons_of_a_run_hold_no_plain_secret_that_the_model_chose_as_a_path(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A password has no form that the mask of secrets finds. The stop comment is public, so the
    reason shows a path only when it names a file of the checkout."""
    secret = "hunter2-Sup3rS3cretPassw0rd"
    script = ModelScript(*(_edit_missing(secret) for _ in range(6)))

    outcome = _step(store, checkout, script)

    assert secret not in outcome.reason
    assert "Last retries of edit_file: File not found: <path> | " in outcome.reason


def test_the_last_reasons_of_a_run_are_cut_to_the_constant_length(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    limit = constants.CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS
    long_name = "d" * (limit - 10)
    path = f"src/{long_name}.py"
    script = ModelScript(tool_calls(write_call(path, "X = 1\n")), _edit_missing(path))

    outcome = _step(store, checkout, script)

    reasons = outcome.reason.rsplit("Last retries of edit_file: ", 1)[1].split(" | ")
    assert [len(reason) for reason in reasons] == [limit + len(" ...")] * 3


def test_a_run_that_ends_on_a_limit_after_retries_names_no_reasons(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(_edit_missing(), tool_call("read_file", path="docs/SAMPLE.md"))

    outcome = _step(store, checkout, script)

    assert outcome.reason.startswith("UsageLimitExceeded")
    assert "Last retries" not in outcome.reason


def test_a_model_that_sends_invalid_arguments_stops_with_no_reasons(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _step(store, checkout, ModelScript(tool_call("read_file")))

    assert "Last retries" not in outcome.reason


def test_a_run_that_reaches_the_request_limit_stops_with_the_message_and_no_count(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_call("read_file", path="docs/SAMPLE.md"))

    outcome = _step(store, checkout, script)

    assert outcome.reason == REQUEST_LIMIT_REASON


def test_a_secret_in_the_message_of_the_error_is_masked_in_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(UnexpectedModelBehavior(f"The reply held {TOKEN} in it."))

    outcome = _step(store, checkout, script)

    assert TOKEN not in outcome.reason
    assert outcome.reason.startswith("UnexpectedModelBehavior: The reply held ")


def test_the_body_of_the_error_stays_out_of_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """`str()` of `UnexpectedModelBehavior` adds its `body`, the text of the model (#2778)."""
    script = ModelScript(UnexpectedModelBehavior("The reply broke the rules.", body="MODEL-TEXT"))

    outcome = _step(store, checkout, script)

    assert outcome.reason == "UnexpectedModelBehavior: The reply broke the rules."


def test_a_long_message_of_the_error_is_cut_and_the_counts_stay_in_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    long = "x" * (3 * constants.CONST_ROADMAP_RUN_ERROR_CHARS)
    script = ModelScript(
        tool_call("shell", command="pytest tests/test_sample.py"), UnexpectedModelBehavior(long)
    )

    outcome = _step(store, checkout, script)

    assert outcome.reason == (
        f"UnexpectedModelBehavior: {'x' * constants.CONST_ROADMAP_RUN_ERROR_CHARS}\n"
        "Refused commands: pytest 1. Other retries: 0."
    )


def test_the_counts_cover_the_repair_turn(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _ruff_fails(programs)
    refused = tool_call("shell", command="pytest tests/test_sample.py")
    script = ModelScript(refused, tool_calls(*WORK), say(FORGOT), refused)

    outcome = _step(store, checkout, script)

    assert outcome.reason.endswith(
        f"\nRefused commands: pytest {CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS + 1}. Other retries: 0."
    )


# ── A model call that fails (#2731) ───────────────────────────────────────────────────────

FAILED_CALLS = [
    pytest.param(ModelAPIError("example-model", "The provider broke."), id="api-error"),
    pytest.param(ModelHTTPError(503, "example-model", {"error": "busy"}), id="http-503"),
    pytest.param(ModelRequestTimeout("example-model", 30), id="timeout"),
]
WORK_WITH_NOTE = ModelResponse(
    parts=[TextPart("I write the test and the code."), *tool_calls(*WORK).parts]
)


@pytest.mark.parametrize("failure", FAILED_CALLS)
def test_a_model_call_that_fails_stops_the_step_with_the_diff_of_the_work_and_the_spend(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, failure: ModelAPIError
) -> None:
    """The requests are the reply to the first request and the request that failed: pydantic-ai
    keeps the failed request as an interrupted reply, with the tokens it was billed."""
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(WORK_WITH_NOTE, failure)

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason.startswith(f"{type(failure).__name__}: "),
        outcome.last_message,
        outcome.requests,
        outcome.input_tokens > 0,
        is_clean_at(checkout, head),
    ) == (StepStatus.STOPPED, True, "I write the test and the code.", 2, True, True)
    assert "diff --git a/src/sample.py b/src/sample.py" in outcome.diff
    assert "diff --git a/tests/test_sample.py b/tests/test_sample.py" in outcome.diff


def test_a_model_call_that_fails_gives_the_status_of_the_reply_and_the_model_in_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(ModelHTTPError(503, "example-model"))

    outcome = _step(store, checkout, script)

    assert outcome.reason == "ModelHTTPError: HTTP 503, model example-model"


def test_a_model_call_that_fails_without_a_status_gives_the_model_in_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(ModelAPIError("example-model", "The provider broke."))

    outcome = _step(store, checkout, script)

    assert outcome.reason == "ModelAPIError: model example-model"


def test_a_model_call_that_runs_past_its_deadline_gives_the_deadline_in_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(ModelRequestTimeout("example-model", 30))

    outcome = _step(store, checkout, script)

    assert (
        outcome.reason
        == "ModelRequestTimeout: model example-model, no complete reply in 30 seconds"
    )


def test_the_reason_of_a_failed_model_call_leaves_out_the_message_and_the_body(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A masker finds a secret by its form in a text. It does not find the value of a key in the
    repr of a dict, so the reason holds neither the body of the reply nor the message."""
    secret = "abcdefghij1234567890zzQQ"
    body = {"error": {"headers": {"x-api-key": secret}, "api_key": secret, "note": TOKEN}}
    script = ModelScript(ModelHTTPError(500, "example-model", body))

    outcome = _step(store, checkout, script)

    assert secret not in outcome.reason
    assert TOKEN not in outcome.reason
    assert "api_key" not in outcome.reason


def test_a_message_of_a_failed_model_call_is_not_in_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(ModelAPIError("example-model", f"The provider echoed {TOKEN}."))

    outcome = _step(store, checkout, script)

    assert outcome.reason == "ModelAPIError: model example-model"


XML_ERROR = "XML syntax error on line 75: unexpected EOF"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"message": XML_ERROR, "type": None, "code": "400"}, id="message"),
        pytest.param({"error": XML_ERROR}, id="error-text"),
        pytest.param({"error": {"message": XML_ERROR, "code": 400}}, id="error-message"),
        pytest.param(XML_ERROR, id="text"),
    ],
)
def test_the_reason_of_a_failed_model_call_holds_the_error_text_of_the_body(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, body: object
) -> None:
    script = ModelScript(ModelHTTPError(400, "example-model", body))

    outcome = _step(store, checkout, script)

    assert outcome.reason == f"ModelHTTPError: HTTP 400, model example-model, body: {XML_ERROR}"


def test_the_error_text_of_the_body_is_masked_and_cut(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    long_text = f"{TOKEN} " + "x" * (2 * constants.CONST_ROADMAP_RUN_ERROR_CHARS)
    script = ModelScript(ModelHTTPError(400, "example-model", {"message": long_text}))

    outcome = _step(store, checkout, script)

    prefix = "ModelHTTPError: HTTP 400, model example-model, body: "
    assert TOKEN not in outcome.reason
    assert outcome.reason.startswith(prefix)
    assert len(outcome.reason) - len(prefix) <= constants.CONST_ROADMAP_RUN_ERROR_CHARS


ECHOES = [
    pytest.param(
        'error parsing tool call: raw=\'{"content":"DB_PASSWORD=hunter2hunter2"}\', err=EOF',
        "error parsing tool call: raw",
        id="ollama-raw-echo",
    ),
    pytest.param(
        {"message": "api_key=abcdef1234567890zz secret: 'S3cr3tValueHere!'"},
        "api_key",
        id="key-value",
    ),
    pytest.param(
        "bad call\nthe second line holds hunter2hunter2 MIIEowIBAAKCAQEA1234567890abcdef",
        "bad call",
        id="second-line",
    ),
    pytest.param(
        "raw='unclosed hunter2hunter2",
        "raw",
        id="unclosed-quote",
    ),
    pytest.param(
        'error parsing tool call: {"content":"DB_PASSWORD: hunter2hunter2xyz"}',
        "error parsing tool call: {<text>:<text>}",
        id="colon-form-echo",
    ),
    pytest.param(
        {
            "message": "x: {'error': 'cannot unmarshal \"db_password: hunter2hunter2\" into a field'}"
        },
        "cannot unmarshal <text> into a field",
        id="colon-form-echo-in-wrapper",
    ),
    pytest.param(
        "token_value 'hunter2hunter2xyz9f8e7d6c' was bad",
        "token_value <text> was bad",
        id="plain-quoted-secret",
    ),
]


@pytest.mark.parametrize(("body", "kept"), ECHOES)
def test_the_error_text_of_the_body_holds_no_echo_of_the_model_output(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, body: object, kept: str
) -> None:
    """A provider can echo what the model wrote. The reason keeps the first line, hides quoted
    words outside the error text of a known gateway wrapper, and stops at the first `=` or `;`,
    as the reason of other errors does (#2562, #2922)."""
    script = ModelScript(ModelHTTPError(400, "example-model", body))

    outcome = _step(store, checkout, script)

    prefix = "ModelHTTPError: HTTP 400, model example-model, body: "
    assert outcome.reason == prefix + kept
    for secret in ("hunter2", "S3cr3t", "abcdef1234", "MIIEow"):
        assert secret not in outcome.reason


GATEWAY_ERROR = (
    "litellm.BadRequestError: Ollama_chatException - KeyError: 'message', "
    "Got unexpected response from Ollama: {'error': 'XML syntax error on line 70: unexpected EOF'}"
)


def test_the_error_text_of_the_gateway_wrapper_is_shown(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The gateway quotes the error text of Ollama in a dict. The stop comment of #2747 showed
    `{<text>: <text>}`, and the cause was not in it (#2922)."""
    script = ModelScript(ModelHTTPError(400, "example-model", {"message": GATEWAY_ERROR}))

    outcome = _step(store, checkout, script)

    assert outcome.reason == (
        "ModelHTTPError: HTTP 400, model example-model, body: "
        "XML syntax error on line 70: unexpected EOF"
    )


def test_a_token_in_the_error_text_of_the_gateway_wrapper_is_masked(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    body = f"Got unexpected response from Ollama: {{'error': 'bad call {TOKEN}'}}"
    script = ModelScript(ModelHTTPError(400, "example-model", {"message": body}))

    outcome = _step(store, checkout, script)

    assert TOKEN not in outcome.reason
    assert outcome.reason.startswith(
        "ModelHTTPError: HTTP 400, model example-model, body: bad call "
    )


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"error": {"api_key": "abcdefghij1234567890zzQQ", "code": 7}}, id="keys"),
        pytest.param({"message": 7, "error": ["abcdefghij1234567890zzQQ"]}, id="not-text"),
        pytest.param(None, id="none"),
    ],
)
def test_a_body_with_no_error_text_adds_nothing_to_the_reason(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, body: object
) -> None:
    script = ModelScript(ModelHTTPError(400, "example-model", body))

    outcome = _step(store, checkout, script)

    assert outcome.reason == "ModelHTTPError: HTTP 400, model example-model"


def test_a_failed_read_of_the_discarded_diff_keeps_the_reason_of_the_stop(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The step has no diff to show. It still tells why it stopped, and why it has no diff."""
    head = git(checkout, "rev-parse", "HEAD")

    def refuse(_source: Path, _start: str) -> tuple[str, bool]:
        raise RoadmapImplementError("git add -A failed.\nfatal: index is locked")

    monkeypatch.setattr(implement_step, "_discarded_diff", refuse)
    _ruff_fails(programs)
    script = ModelScript(tool_calls(*WORK), say(FORGOT), ModelAPIError("example-model", "broke"))

    outcome = _step(store, checkout, script)

    assert outcome.status is StepStatus.STOPPED
    assert outcome.reason.startswith("ModelAPIError: model example-model\n")
    assert "fatal: index is locked" in outcome.reason
    assert (outcome.diff, outcome.diff_cut, is_clean_at(checkout, head)) == ("", False, True)


@pytest.mark.parametrize("failure", FAILED_CALLS)
def test_a_model_call_that_fails_in_the_repair_turn_stops_the_step_with_the_diff_of_both_turns(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, failure: ModelAPIError
) -> None:
    """A check fails in the first turn, and the repair turn fails: the diff is the work."""
    head = git(checkout, "rev-parse", "HEAD")
    _ruff_fails(programs)
    script = ModelScript(tool_calls(*WORK), say(FORGOT), failure)

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason.startswith(f"{type(failure).__name__}: "),
        outcome.last_message,
        outcome.requests,
        is_clean_at(checkout, head),
    ) == (StepStatus.STOPPED, True, FORGOT, 3, True)
    assert "diff --git a/src/sample.py b/src/sample.py" in outcome.diff
    assert "diff --git a/tests/test_sample.py b/tests/test_sample.py" in outcome.diff


def test_the_spend_of_a_failed_repair_turn_is_in_the_ledger(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, spend_ledger: SpendLedger
) -> None:
    _ruff_fails(programs)
    script = ModelScript(
        tool_calls(*WORK),
        say(FORGOT),
        tool_call("read_file", path="docs/SAMPLE.md"),
        ModelAPIError("example-model", "The provider broke."),
    )

    outcome = _step(store, checkout, script)

    assert (_spend_rows(spend_ledger), outcome.requests) == (
        [("agent_run", "implement", 1, 1), ("agent_run", "implement", 1, 1)],
        4,
    )


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_key_in_the_repair_turn_raises_after_the_checkout_is_reset(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, status: int
) -> None:
    _ruff_fails(programs)
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_calls(*WORK), say(FORGOT), ModelHTTPError(status, "example-model", {"error": "no"})
    )

    with pytest.raises(AICredentialsError) as raised:
        _step(store, checkout, script)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"

    assert is_clean_at(checkout, head)


# ── A model call that fails inside a stream is sent again (#2794) ─────────────────────────


def _in_stream_400() -> InStream:
    """The error that the gateway sends when Ollama cannot read a tool call of the model: the
    stream is open, so the status 200 is sent, and the error object has the code "400"."""
    body = {"message": XML_ERROR, "type": None, "param": None, "code": "400"}
    return InStream(ModelHTTPError(400, "example-model", body, in_stream=True))


def _history(messages: Sequence[Any]) -> list[Any]:
    return [message.parts for message in messages]


def _asks_for_a_smaller_edit(sent: Sequence[Any], failed: Sequence[Any]) -> bool:
    """Whether `sent` is the request of `failed` with one more part at its end: the text that asks
    for a smaller edit. A tool call that the provider cannot parse fails again for the same
    conversation, so the request that follows it must differ (#3053)."""
    *earlier, last = _history(sent)
    *before, failed_last = _history(failed)
    return (
        earlier == before
        and last[:-1] == failed_last
        and last[-1].content == MESSAGES.roadmap.implement_parser_smaller_edit
    )


def test_a_400_inside_a_stream_is_sent_again_with_the_same_history_and_the_step_ends_done(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(*the_whole_group()), _in_stream_400(), say("The group is done.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.last_message) == (
        StepStatus.DONE,
        "",
        "The group is done.",
    )
    assert len(script.seen) == 3
    assert _asks_for_a_smaller_edit(script.seen[2], script.seen[1])


def test_a_400_inside_a_stream_at_the_first_request_is_sent_again(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(_in_stream_400(), tool_calls(*the_whole_group()), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, len(script.seen)) == (StepStatus.DONE, 3)
    assert _asks_for_a_smaller_edit(script.seen[1], script.seen[0])


def test_a_400_inside_a_stream_on_every_send_stops_the_step_with_the_body(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_calls(*WORK), _in_stream_400())

    outcome = _step(store, checkout, script)

    first, named = outcome.reason.splitlines()
    assert (outcome.status, first, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        f"ModelHTTPError: HTTP 400, model example-model, body: {XML_ERROR}",
        True,
    )
    assert "tool call parsing failed" in named
    assert len(script.seen) == 1 + 1 + constants.CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS
    assert outcome.failure_class is FailureClass.PARSER
    assert "diff --git a/src/sample.py b/src/sample.py" in outcome.diff


NOT_RESENT = [
    pytest.param(
        ModelHTTPError(400, "example-model", {"message": XML_ERROR}), id="before-the-stream"
    ),
    pytest.param(
        ModelHTTPError(503, "example-model", {"message": "busy"}, in_stream=True),
        id="status-503",
    ),
    pytest.param(
        ModelHTTPError.for_category(
            ModelContextWindowExceededError,
            status_code=400,
            model_name="example-model",
            body={"message": "The prompt is too long."},
            in_stream=True,
        ),
        id="context-window",
    ),
]


@pytest.mark.parametrize("failure", NOT_RESENT)
def test_other_failed_model_calls_are_not_sent_again(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, failure: ModelHTTPError
) -> None:
    script = ModelScript(tool_calls(*WORK), InStream(failure))

    outcome = _step(store, checkout, script)

    assert (outcome.status, len(script.seen)) == (StepStatus.STOPPED, 2)
    assert "tool call parsing failed" not in outcome.reason


def test_a_400_inside_a_stream_in_the_repair_turn_is_sent_again(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _ruff_fails_once(programs)
    script = ModelScript(
        tool_calls(*WORK), say(FORGOT), _in_stream_400(), tool_calls(TICK), say("Ticked.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.last_message) == (StepStatus.DONE, "Ticked.")
    assert _asks_for_a_smaller_edit(script.seen[3], script.seen[2])


def test_a_second_parser_failure_in_one_step_stops_it_after_a_good_reply(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The smaller edit is asked once in a step (#3053). A parser failure after a good reply is the
    second one, so the step stops and sends no request again."""
    script = ModelScript(
        _in_stream_400(), tool_calls(*the_whole_group()), _in_stream_400(), say("Done.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.failure_class) == (StepStatus.STOPPED, FailureClass.PARSER)
    assert len(script.seen) == 3
    assert _asks_for_a_smaller_edit(script.seen[1], script.seen[0])


def test_a_failure_after_a_good_reply_stops_without_a_second_smaller_edit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    read = tool_call("read_file", path="docs/SAMPLE.md")
    script = ModelScript(_in_stream_400(), read, _in_stream_400())

    outcome = _step(store, checkout, script)

    assert outcome.status == StepStatus.STOPPED
    assert f"body: {XML_ERROR}" in outcome.reason
    assert len(script.seen) == 3


def test_the_replies_before_a_send_again_count_against_the_request_limit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A fresh budget for the second send would let the run make more requests than the limit."""
    read = tool_call("read_file", path="docs/SAMPLE.md")
    script = ModelScript(read, _in_stream_400(), read)

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.STOPPED, REQUEST_LIMIT_REASON)
    assert len(script.seen) == CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS


def test_the_tool_calls_before_a_send_again_count_against_the_tool_call_limit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    batch = 4
    reads = tool_calls(*[("read_file", {"path": "docs/SAMPLE.md"})] * batch)
    script = ModelScript(reads, _in_stream_400(), reads)

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (StepStatus.STOPPED, TOOL_CALL_LIMIT_REASON)
    assert len(script.seen) == CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS // batch + 2


def test_the_spend_of_a_failed_send_is_in_the_outcome_and_the_ledger(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake, spend_ledger: SpendLedger
) -> None:
    script = ModelScript(_in_stream_400(), tool_calls(*the_whole_group()), say("Done."))

    outcome = _step(store, checkout, script)

    assert outcome.requests == 3
    assert [row[:2] for row in _spend_rows(spend_ledger)] == [("agent_run", "implement")] * 2


# ── The fix step (#2665) ──────────────────────────────────────────────────────────────────

FIX_TITLE = "Make check Static Analysis pass"


def _fix(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript, log: str = "E501 line"
) -> StepOutcome:
    return run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="Static Analysis", log=log),
        source=checkout,
        model=script.model(),
        window=WINDOW,
    )


def test_the_inputs_of_a_fix_step_hold_the_log_of_the_check_under_a_group_that_names_it(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    fix = FixRequest(check="Static Analysis", log="E501 line too long")

    inputs = build_step_inputs(store, item=1, group=0, source=checkout, window=WINDOW, fix=fix)

    assert (
        inputs.group.number,
        inputs.group.title,
        inputs.group.verification_commands,
        "# The log of the failed check\n\nE501 line too long" in inputs.message,
        "Make check `Static Analysis` pass" in inputs.message,
    ) == (
        0,
        FIX_TITLE,
        ("uv run devops ci test tests/test_sample.py", "uv run devops docs check"),
        True,
        True,
    )


def test_the_log_of_a_fix_step_is_cut_to_its_last_characters(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    long_log = "FIRST" + "x" * CONST_ROADMAP_IMPLEMENT_LOG_CHARS + "LAST"
    fix = FixRequest(check="Static Analysis", log=long_log)

    inputs = build_step_inputs(store, item=1, group=0, source=checkout, window=WINDOW, fix=fix)

    assert ("LAST" in inputs.message, "FIRST" in inputs.message) == (True, False)


def test_a_fix_step_commits_the_fix_with_the_tasks_as_they_were(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    before = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_calls(write_call("src/sample.py", SHOUT_CODE)), say("Fixed."))

    outcome = _fix(store, checkout, script)

    assert (
        outcome.status,
        outcome.group,
        outcome.title,
        outcome.reason,
        git(checkout, "rev-parse", "HEAD~1"),
        git(checkout, "log", "-1", "--format=%s"),
        git(checkout, "show", "--name-only", "--format=", "HEAD"),
    ) == (
        StepStatus.DONE,
        0,
        FIX_TITLE,
        "",
        before,
        f"chore: {FIX_TITLE} (#1)",
        "src/sample.py",
    )


def test_a_fix_step_runs_the_verification_commands_of_every_group_of_the_change(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _fix(
        store,
        checkout,
        ModelScript(tool_calls(write_call("src/sample.py", SHOUT_CODE)), say("Ok.")),
    )

    uv = [command_text(call) for call in programs.calls if call.argv[0] == "uv"]
    assert uv[1:3] == ["uv run devops ci test tests/test_sample.py", "uv run devops docs check"]


def test_a_fix_step_that_ticks_a_task_ends_done_with_the_tasks_as_they_were(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(write_call("src/sample.py", SHOUT_CODE), write_call(TASKS_PATH, TICKED)),
        say("Fixed."),
    )

    outcome = _fix(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        git(checkout, "show", "--name-only", "--format=", "HEAD"),
        (checkout / TASKS_PATH).read_text(encoding="utf-8"),
    ) == (StepStatus.DONE, "", "src/sample.py", TASKS)


def test_a_fix_step_that_changes_no_file_stops(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _fix(store, checkout, ModelScript(say("Nothing to fix.")))

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        "The agent changed no file.",
    )


# ── No process of the agent lives when the job runs a program with the token ──────────────


@pytest.mark.live("sleep")
def test_no_process_of_the_agent_is_alive_when_git_runs_after_the_step_in_a_runner(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `git` or `gh` child of the job gets the session token in its environment, which a process
    of the same user can read through `/proc/<pid>/environ`. The agent's shell is such a process,
    and it can leave one behind that polls `/proc`. So the step ends every process of the agent
    before the job runs a program with the token (#2667)."""
    config(roadmap={"implement": {"in_runner": True}})
    leftovers: list[subprocess.Popen[bytes]] = []
    alive_at_git: list[bool] = []

    def fake_end_leftover_processes(timeout: float = 5.0) -> None:
        for p in leftovers:
            p.kill()
            p.wait()

    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_step.end_leftover_processes",
        fake_end_leftover_processes,
    )

    def leave_a_process() -> None:
        leftovers.append(subprocess.Popen(["sleep", "60"], start_new_session=True))

    def git_and_look(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        alive_at_git.extend(p.poll() is None for p in leftovers)
        return git_for_real(call)

    programs.answer("git", ProcessAnswer(side_effect=git_and_look))
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), effects={2: leave_a_process})
    try:
        _step(store, checkout, script)
    finally:
        for process in leftovers:
            process.kill()
            process.wait()

    assert (len(leftovers), alive_at_git, [p.poll() is None for p in leftovers]) == (
        1,
        [False] * len(alive_at_git),
        [False],
    )
    assert alive_at_git


def test_a_process_that_survives_the_end_of_the_step_stops_the_step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config(roadmap={"implement": {"in_runner": True}})

    def refuse() -> None:
        raise RoadmapImplementError("a process of the agent survived")

    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_step.end_leftover_processes", refuse
    )

    with pytest.raises(RoadmapImplementError, match="survived"):
        _step(store, checkout, ModelScript(say("Done.")))


# ── The model tier ladder (#3060) ─────────────────────────────────────────────────────────


def test_a_provider_error_on_tier_one_moves_the_step_to_tier_two_and_succeeds(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    """The failed attempt spends no repair round, and the trace names both tiers."""
    config(roadmap={"implement": {"ladder": {"edit": ["devops-coder", "devops-reasoning"]}}})
    script = ModelScript(
        ModelAPIError("example-model", "The provider broke."),
        tool_calls(*the_whole_group()),
        say("Done."),
    )

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        outcome.repair_rounds,
        outcome.tier,
        outcome.tiers,
    ) == (StepStatus.DONE, "", 0, "devops-reasoning", ("devops-coder", "devops-reasoning"))
    assert outcome.tier_spend["devops-coder"].requests >= 1
    assert outcome.tier_spend["devops-reasoning"].input_tokens > 0
    assert outcome.tier_spend["devops-reasoning"].output_tokens > 0


def test_a_parser_failure_moves_the_step_to_the_next_tier_without_a_repair_round(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"ladder": {"edit": ["devops-coder", "devops-reasoning"]}}})
    script = ModelScript(
        UnexpectedModelBehavior("Ollama_chatException: failed to parse the tool call"),
        tool_calls(*the_whole_group()),
        say("Done."),
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.repair_rounds, outcome.tiers) == (
        StepStatus.DONE,
        0,
        ("devops-coder", "devops-reasoning"),
    )


def test_an_unhealthy_tier_is_skipped(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        ladder=["devops-coder", "devops-reasoning"],
        tier_health=lambda names: {"devops-coder": False, "devops-reasoning": True},
    )

    assert (outcome.status, outcome.tier, outcome.tiers) == (
        StepStatus.DONE,
        "devops-reasoning",
        ("devops-reasoning",),
    )


def test_a_fix_step_runs_the_repair_ladder(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"ladder": {"repair": ["devops-coder", "devops-reasoning"]}}})
    script = ModelScript(
        ModelAPIError("example-model", "The provider broke."),
        tool_calls(write_call("src/sample.py", SHOUT_CODE)),
        say("Fixed."),
    )

    outcome = _fix(store, checkout, script)

    assert (outcome.status, outcome.tiers) == (
        StepStatus.DONE,
        ("devops-coder", "devops-reasoning"),
    )


def test_a_step_with_no_ladder_runs_on_the_model_it_was_given(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = run_step(
        store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW, ladder=[]
    )

    assert (outcome.status, outcome.tier, outcome.tiers) == (StepStatus.DONE, "", ())


def test_a_reading_of_no_healthy_tier_uses_the_first_tier(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        ladder=["devops-coder", "devops-reasoning"],
        tier_health=lambda names: dict.fromkeys(names, False),
    )

    assert (outcome.status, outcome.tier, outcome.tiers) == (
        StepStatus.DONE,
        "devops-coder",
        ("devops-coder",),
    )


def test_the_step_reads_the_gateway_health_when_the_provider_is_the_gateway(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config(
        ai={"provider": "gateway", "gateway_url": "https://gateway.example.com"},
        roadmap={"implement": {"ladder": {"edit": ["devops-coder", "devops-reasoning"]}}},
    )
    calls: list[tuple[str, ...]] = []

    def health(_self: object, names: Sequence[str], timeout: float = 9.0) -> dict[str, bool]:
        calls.append(tuple(names))
        return {"devops-coder": False, "devops-reasoning": True}

    monkeypatch.setattr("devops_cli.ai.gateway.GatewayRouter.tier_health", health)
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.tier, calls) == ("devops-reasoning", [("devops-coder", "devops-reasoning")])


def test_a_step_with_no_model_and_no_tier_factory_is_refused(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    with pytest.raises(RoadmapImplementError, match="needs a model"):
        run_step(store, item=1, group=1, source=checkout, window=WINDOW)
