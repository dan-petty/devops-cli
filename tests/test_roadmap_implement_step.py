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
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai_harness.shell import Shell

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.commands import IMPLEMENT_SHELL_PROGRAMS
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_LOG_CHARS,
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
    CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    build_agent,
    build_step_inputs,
    parse_task_groups,
    run_fix_step,
    run_step,
    shell_environment,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import (
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
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_call, tool_calls

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
        "  - Verification: `uv run devops ci test tests/test_sample.py` and `uv run devops docs check`",
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
        "The first group (#1)",
        [TASKS_PATH, "src/sample.py", "tests/test_sample.py"],
        "",
    )


def test_the_exit_checks_run_each_command_once_then_the_static_checks_on_the_changed_files(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    py = "src/sample.py tests/test_sample.py"
    uv = [call for call in programs.calls if call.argv[0] == "uv"]
    assert ([command_text(call) for call in uv], {call.cwd for call in uv}) == (
        [
            "uv run devops ci test tests/test_sample.py",
            "uv run devops docs check",
            f"uv run ruff check {py}",
            f"uv run ruff format --check {py}",
            f"uv run mypy --strict {py}",
        ],
        {checkout},
    )


def test_a_failed_verification_command_stops_the_step_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    programs.answer(
        lambda call: command_text(call) == DOCS, ProcessAnswer(returncode=1, stdout="no docs\n")
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
        f"{DOCS} exited with status 1.\nno docs",
        "",
        True,
        False,
        False,
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

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "uv run ruff check src/sample.py tests/test_sample.py exited with status 1.\nE501 too long",
        True,
    )


def test_a_task_left_unticked_stops_the_step_before_any_command_runs(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_calls(write_call("src/sample.py", SHOUT_CODE)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        programs_run(programs, "uv"),
        is_clean_at(checkout, head),
    ) == (
        StepStatus.STOPPED,
        "A task of the group is not ticked: [ ] Add the failing test `tests/test_sample.py` for `src/sample.py`",
        [],
        True,
    )


def test_a_change_to_another_group_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    other = TICKED.replace("- [x] Document", "- [ ] Document")
    script = ModelScript(tool_calls(write_call(TASKS_PATH, other)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "Group 2 changed. A step may change only its own group.",
        True,
    )


def test_a_task_that_the_agent_removes_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    shorter = TICKED.replace(
        "- [x] Add `shout` to `src/sample.py`\n"
        "  - Verification: `uv run devops ci test tests/test_sample.py` and `uv run devops docs check`\n",
        "",
    )
    script = ModelScript(tool_calls(write_call(TASKS_PATH, shorter)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "The tasks of group 1 changed. A step may only tick them.",
        True,
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
        "The verification command uv run 'devops is not a valid command line.",
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
        "The verification command curl http://example.com is not allowed. curl is not one of: "
        "git, uv, ruff, mypy, openspec, devops.",
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
    hook = checkout / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho refused by the hook\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "The commit failed.\nrefused by the hook",
        True,
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
            "Command 'curl' is not in the allowed list.",
            "Shell operator ';' is not allowed.",
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
        "Command 'devops' is not in the allowed list.",
        "Command 'openspec' is not in the allowed list.",
    ]


def test_the_shell_runs_with_a_scratch_home_and_the_cache_of_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No git configuration, helper or key of the user's home reaches a shell command."""
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    monkeypatch.delenv("UV_PYTHON", raising=False)

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


def test_the_agent_of_a_step_runs_its_shell_in_that_environment(
    tmp_path: Path, checkout: Path
) -> None:
    agent = build_agent(ModelScript(say("x")).model(), checkout, "go", WINDOW, tmp_path / "home")

    leaves: list[Any] = []

    def collect(leaf: Any) -> Any:
        leaves.append(leaf)
        return leaf

    agent.root_capability.visit_and_replace(collect)

    shells = [leaf for leaf in leaves if isinstance(leaf, Shell)]
    assert [shell.env for shell in shells] == [shell_environment(tmp_path / "home")]
    assert [shell.allowed_commands for shell in shells] == [list(IMPLEMENT_SHELL_PROGRAMS)]


def test_a_commit_that_the_agent_makes_stops_the_step_and_the_checkout_returns_to_its_start(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The shell allowlist admits git, so the agent can commit. Its effect is scripted here."""
    head = git(checkout, "rev-parse", "HEAD")
    moved: list[str] = []

    def agent_commits() -> None:
        git(checkout, "add", "-A")
        git(checkout, "commit", "-q", "-m", "own commit")
        moved.append(git(checkout, "rev-parse", "HEAD"))

    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), effects={2: agent_commits})

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.commit, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        f"The agent moved HEAD from {head} to {moved[0]}. A step makes the only commit.",
        "",
        True,
    )


def test_a_tasks_file_that_the_agent_removes_stops_the_step_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_calls(*the_whole_group()),
        say("Done."),
        effects={2: (checkout / TASKS_PATH).unlink},
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "The tasks of group 1 changed. A step may only tick them.",
        True,
    )


def test_a_tasks_file_with_bytes_that_are_not_text_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")

    def garble() -> None:
        (checkout / TASKS_PATH).write_bytes(b"\xff\xfe not utf-8")

    script = ModelScript(say("Done."), effects={1: garble})

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "The tasks of group 1 changed. A step may only tick them.",
        True,
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
        "UsageLimitExceeded",
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
        "UsageLimitExceeded",
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

    with pytest.raises(AICredentialsError):
        _step(store, checkout, script)

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
        f"{FIX_TITLE} (#1)",
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
    assert uv[:2] == ["uv run devops ci test tests/test_sample.py", "uv run devops docs check"]


def test_a_fix_step_that_ticks_a_task_stops_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_calls(write_call("src/sample.py", SHOUT_CODE), write_call(TASKS_PATH, TICKED)),
        say("Fixed."),
    )

    outcome = _fix(store, checkout, script)

    assert (outcome.status, outcome.reason, is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "The tasks changed. A fix step changes no task.",
        True,
    )


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
) -> None:
    """A `git` or `gh` child of the job gets the session token in its environment, which a process
    of the same user can read through `/proc/<pid>/environ`. The agent's shell is such a process,
    and it can leave one behind that polls `/proc`. So the step ends every process of the agent
    before the job runs a program with the token (#2667)."""
    config(roadmap={"implement": {"in_runner": True}})
    leftovers: list[subprocess.Popen[bytes]] = []
    alive_at_git: list[bool] = []

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

    monkeypatch.setattr("devops_cli.roadmap.implement_step.end_leftover_processes", refuse)

    with pytest.raises(RoadmapImplementError, match="survived"):
        _step(store, checkout, ModelScript(say("Done.")))
