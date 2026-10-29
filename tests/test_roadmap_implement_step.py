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
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.exceptions import ModelHTTPError

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
    CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.roadmap.implement_step import (
    StepOutcome,
    StepStatus,
    build_step_inputs,
    parse_task_groups,
    run_step,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.model_script import ModelScript, say, tool_call, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
WINDOW = 128000

_TASKS = """\
# Tasks

## 1. The first group

- [ ] Add the failing test `tests/test_sample.py` for `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py`
- [ ] Add `shout` to `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py` and `uv run devops docs check`

## 2. The second group

- [x] Document the function in `docs/SAMPLE.md`
  - Verification: `uv run devops docs check`

## Workflow follow-up

- A plain bullet with `src/other.py` in it.
"""

_BODY = """\
## Problem or Motivation

The sample cannot shout.

## Proposed Solution & Architectural Design

A long design that the step does not need.

## Acceptance criteria

- `shout("a")` returns `A!`.

## Target Subsystem

Nothing else.
"""

_SAMPLE = '''\
"""A sample module."""


def hello(name: str) -> str:
    """Greet `name`."""
    return f"hello {name}"
'''


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def make_checkout(root: Path, tasks: str = _TASKS) -> Path:
    """A git checkout whose one commit holds change `1-sample-change` and two source files."""
    checkout = root / "checkout"
    change = checkout / "openspec" / "changes" / "1-sample-change"
    change.mkdir(parents=True)
    (checkout / "src").mkdir()
    (checkout / "docs").mkdir()
    (checkout / "tests").mkdir()
    (checkout / "tests" / "conftest.py").write_text('"""The tests."""\n', encoding="utf-8")
    git(checkout, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        git(checkout, "config", key, value)
    git(checkout, "config", "commit.gpgsign", "false")
    (change / "proposal.md").write_text("# Proposal\n\nWhy the sample shouts.\n", encoding="utf-8")
    (change / "design.md").write_text("# Design\n\nShout in capitals.\n", encoding="utf-8")
    (change / "tasks.md").write_text(tasks, encoding="utf-8")
    (checkout / "src" / "sample.py").write_text(_SAMPLE, encoding="utf-8")
    (checkout / "src" / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
    (checkout / "docs" / "SAMPLE.md").write_text("The sample.\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "init")
    return checkout


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A private roadmap whose item 1 is the sample item."""
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=True)
    roadmap.seed_issue(
        "Make the sample shout",
        body=_BODY,
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    return roadmap


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    return make_checkout(tmp_path)


# ── The groups of a tasks.md ──────────────────────────────────────────────────────────────


def test_a_tasks_file_holds_numbered_groups_with_their_tasks_commands_and_files() -> None:
    groups = parse_task_groups(_TASKS)

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
    first, second = parse_task_groups(_TASKS)

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

_TASKS_PATH = "openspec/changes/1-sample-change/tasks.md"
_TICKED = _TASKS.replace("- [ ] Add", "- [x] Add")
_TEST = "def test_shout() -> None:\n    assert True\n"
_CODE = _SAMPLE + '\n\ndef shout(text: str) -> str:\n    return text.upper() + "!"\n'
_CHECK = "uv run devops ci test tests/test_sample.py"
_DOCS = "uv run devops docs check"


def _write(path: str, content: str) -> tuple[str, dict[str, Any]]:
    return "write_file", {"path": path, "content": content}


def _the_whole_group() -> tuple[tuple[str, dict[str, Any]], ...]:
    """The calls of an agent that writes the test and the code, and ticks the group's tasks."""
    return (
        _write("tests/test_sample.py", _TEST),
        _write("src/sample.py", _CODE),
        _write(_TASKS_PATH, _TICKED),
    )


def _git_for_real(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 B607: git, on the temporary repository of the test
        call.argv, cwd=call.cwd, capture_output=True, text=True, check=False
    )


@pytest.fixture
def programs(process_fake: ProcessFake) -> ProcessFake:
    """The process edge: git runs for real, and every other program exits 0 unless a test says
    otherwise."""
    process_fake.answer("git", ProcessAnswer(side_effect=_git_for_real))
    return process_fake


def _step(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript, group: int = 1
) -> StepOutcome:
    return run_step(
        store, item=1, group=group, source=checkout, model=script.model(), window=WINDOW
    )


_PREVIEW = ("--preview-features", "malware-check,check-command")


def _text(call: ProcessCall) -> str:
    """The command line of a call, without the preview flags that the runner adds to uv."""
    return " ".join(word for word in call.argv if word not in _PREVIEW)


def _programs_run(fake: ProcessFake, program: str) -> list[str]:
    return [_text(call) for call in fake.calls if call.argv[0] == program]


def _is_clean_at(checkout: Path, head: str) -> bool:
    return (git(checkout, "rev-parse", "HEAD"), git(checkout, "status", "--porcelain")) == (
        head,
        "",
    )


def test_a_group_that_the_agent_completes_ends_done_with_one_commit(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    before = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_calls(*_the_whole_group()),
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
        [_TASKS_PATH, "src/sample.py", "tests/test_sample.py"],
        "",
    )


def test_the_exit_checks_run_each_command_once_then_the_static_checks_on_the_changed_files(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _step(store, checkout, ModelScript(tool_calls(*_the_whole_group()), say("Done.")))

    py = "src/sample.py tests/test_sample.py"
    uv = [call for call in programs.calls if call.argv[0] == "uv"]
    assert ([_text(call) for call in uv], {call.cwd for call in uv}) == (
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
        lambda call: _text(call) == _DOCS, ProcessAnswer(returncode=1, stdout="no docs\n")
    )
    script = ModelScript(tool_calls(*_the_whole_group()), say("Done."))

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        outcome.commit,
        _is_clean_at(checkout, head),
        (checkout / "tests" / "test_sample.py").exists(),
        "def shout" in (checkout / "src" / "sample.py").read_text(encoding="utf-8"),
    ) == (
        StepStatus.STOPPED,
        f"{_DOCS} exited with status 1.\nno docs",
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
        lambda call: _text(call).startswith("uv run ruff check"),
        ProcessAnswer(returncode=1, stdout="E501 too long\n"),
    )

    outcome = _step(store, checkout, ModelScript(tool_calls(*_the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.reason, _is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "uv run ruff check src/sample.py tests/test_sample.py exited with status 1.\nE501 too long",
        True,
    )


def test_a_task_left_unticked_stops_the_step_before_any_command_runs(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(tool_calls(_write("src/sample.py", _CODE)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        _programs_run(programs, "uv"),
        _is_clean_at(checkout, head),
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
    other = _TICKED.replace("- [x] Document", "- [ ] Document")
    script = ModelScript(tool_calls(_write(_TASKS_PATH, other)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, _is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "Group 2 changed. A step may change only its own group.",
        True,
    )


def test_a_task_that_the_agent_removes_stops_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    shorter = _TICKED.replace(
        "- [x] Add `shout` to `src/sample.py`\n"
        "  - Verification: `uv run devops ci test tests/test_sample.py` and `uv run devops docs check`\n",
        "",
    )
    script = ModelScript(tool_calls(_write(_TASKS_PATH, shorter)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, _is_clean_at(checkout, head)) == (
        StepStatus.STOPPED,
        "The tasks of group 1 changed. A step may only tick them.",
        True,
    )


def test_a_verification_command_that_is_no_command_line_does_not_run(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    tasks = _TASKS.replace(_DOCS, "uv run 'devops")
    checkout = make_checkout(tmp_path, tasks)
    ticked = tasks.replace("- [ ] Add", "- [x] Add")
    script = ModelScript(tool_calls(_write(_TASKS_PATH, ticked)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason) == (
        StepStatus.STOPPED,
        "The verification command uv run 'devops is not a valid command line.",
    )


def test_a_verification_command_outside_the_allowlist_does_not_run(
    store: InMemoryRoadmapStore, tmp_path: Path, programs: ProcessFake
) -> None:
    tasks = _TASKS.replace(_DOCS, "curl http://example.com")
    checkout = make_checkout(tmp_path, tasks)
    ticked = tasks.replace("- [ ] Add", "- [x] Add")
    script = ModelScript(tool_calls(_write(_TASKS_PATH, ticked)), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, _programs_run(programs, "curl")) == (
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

    outcome = _step(store, checkout, ModelScript(tool_calls(*_the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.reason, _is_clean_at(checkout, head)) == (
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
        tool_call("write_file", path="tests/test_sample.py", content=_TEST),
        tool_call("read_file", path="docs/SAMPLE.md"),
    )

    outcome = _step(store, checkout, script)

    assert (
        outcome.status,
        outcome.reason,
        outcome.requests,
        len(script.seen),
        _is_clean_at(checkout, head),
    ) == (
        StepStatus.STOPPED,
        "UsageLimitExceeded",
        CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
        CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
        True,
    )


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
        tool_call("write_file", path="tests/test_sample.py", content=_TEST),
        ModelHTTPError(401, "gateway", {"error": "bad key"}),
    )

    with pytest.raises(AICredentialsError):
        _step(store, checkout, script)

    assert _is_clean_at(checkout, head)


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
