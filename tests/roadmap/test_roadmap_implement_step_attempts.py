"""The attempts of a step (#3053): each one is an event of the trace with its outcome, its class and
its evidence; a failure that no attempt can fix gets no repair round; and a step that used all its
rounds says so in its reason.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`. `ruff check` reads the files of the checkout through `process_fake`, so a file that
holds `import os` fails the lint.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.roadmap.explain import render_trace
from devops_cli.roadmap.implement_step import run_step
from devops_cli.roadmap.implement_trace import ImplementTrace, TraceEvent, TraceEventKind, decode
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import (
    CHECK,
    SHOUT_CODE,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    tool_reads,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

BAD_TEST = "import os\n\n" + TEST_BODY
UNUSED = "F401 `os` imported but unused\n --> tests/test_sample.py:1:8"
FIRST = tool_calls(
    write_call("tests/test_sample.py", BAD_TEST),
    write_call("src/sample.py", SHOUT_CODE),
    write_call(TASKS_PATH, TICKED),
)
FIX = tool_calls(write_call("tests/test_sample.py", TEST_BODY))


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _lint_fails_on_an_unused_import(programs: ProcessFake) -> None:
    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=tool_reads("import os", UNUSED)),
    )


def _run(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript, group: int = 1
) -> tuple[ImplementTrace, str, int]:
    trace = ImplementTrace(step=f"group {group}")
    outcome = run_step(
        store,
        item=1,
        group=group,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        trace=trace,
    )
    return trace, outcome.reason, outcome.requests


def _attempts(trace: ImplementTrace) -> list[dict[str, object]]:
    return [event.fields for event in trace.events if event.kind is TraceEventKind.ATTEMPT]


def test_a_failing_check_that_passes_on_the_second_attempt_shows_both_attempts(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    _lint_fails_on_an_unused_import(programs)
    script = ModelScript(FIRST, say("Done."), FIX, say("Removed the import."))

    trace, reason, _ = _run(store, checkout, script)

    first, second = _attempts(trace)
    assert reason == ""
    assert (first["number"], first["outcome"], first["class"], first["next"]) == (
        1,
        "failed",
        "lint",
        "repair",
    )
    assert "F401" in str(first["evidence"])
    assert (second["number"], second["outcome"], second["next"]) == (2, "passed", "stop")
    assert "class" not in second


def test_a_failure_that_stays_ends_the_last_attempt_with_stop_and_names_the_rounds(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"repair_rounds": 1}})
    _lint_fails_on_an_unused_import(programs)
    script = ModelScript(FIRST, say("Done."), say("No change."))

    trace, reason, _ = _run(store, checkout, script)

    assert [(a["number"], a["outcome"], a["next"]) for a in _attempts(trace)] == [
        (1, "failed", "repair"),
        (2, "failed", "stop"),
    ]
    first, _, last = reason.partition("\n")
    assert "F401" in reason
    assert last.splitlines()[-1] == (
        "The step used all its repair rounds: `roadmap.implement.repair_rounds=1`."
    )
    assert first


def test_a_failed_verification_command_gets_no_round_and_names_no_rounds(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    programs.answer(
        lambda call: command_text(call) == CHECK,
        ProcessAnswer(returncode=1, stdout="1 failed"),
    )
    script = ModelScript(FIRST, say("Done."))

    trace, reason, requests = _run(store, checkout, script)

    assert "repair_rounds" not in reason
    assert requests == 2
    assert [(a["number"], a["next"]) for a in _attempts(trace)] == [(1, "stop")]


def test_a_group_that_changes_no_file_is_one_attempt_of_class_plan_defect(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(say("Nothing to do."))

    trace, reason, requests = _run(store, checkout, script, group=2)

    assert (requests, reason) == (1, "The agent changed no file.")
    assert _attempts(trace) == [
        {
            "number": 1,
            "tier": "devops-coder",
            "outcome": "failed",
            "next": "stop",
            "class": "plan_defect",
            "evidence": "The agent changed no file.",
        }
    ]


def test_an_attempt_event_is_masked_and_survives_the_encoding() -> None:
    trace = ImplementTrace(step="group 1")

    trace.attempt(
        2,
        "devops-coder",
        "lint",
        "Bearer abcdefghijklmnopqrstuvwxyz0123 at db.corp.internal",
        repair=False,
    )

    text = trace.encode()
    event = decode(text).events[0]
    assert "abcdefghijklmnopqrstuvwxyz0123" not in text
    assert "db.corp.internal" not in text
    assert (event.kind, event.fields["tier"], event.fields["next"]) == (
        TraceEventKind.ATTEMPT,
        "devops-coder",
        "stop",
    )


def test_the_trace_option_prints_an_attempt_as_one_line() -> None:
    trace = ImplementTrace(
        events=[
            TraceEvent(
                TraceEventKind.ATTEMPT,
                "group 1",
                {
                    "number": 1,
                    "tier": "devops-coder",
                    "outcome": "failed",
                    "class": "lint",
                    "evidence": "F401 unused import",
                    "next": "repair",
                },
            ),
            TraceEvent(
                TraceEventKind.ATTEMPT,
                "group 1",
                {"number": 2, "tier": "", "outcome": "passed", "next": "stop"},
            ),
        ]
    )

    assert render_trace(trace, number=7).splitlines() == [
        "group 1: attempt 1 on devops-coder, failed (lint): F401 unused import, next: repair",
        "group 1: attempt 2, passed, next: stop",
    ]
