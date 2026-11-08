"""The failure taxonomy of the implement job (#3065): the classifier, and the table of default
actions.

The classifier is a pure function, so these tests give it text and read the class. The excerpts
marked with an issue number are real: they are the text of a stop comment, an agent message or a
pull request in that issue. The others are the messages that the job itself writes for the cause.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from devops_cli.ai.client.models import AIClientError, StructuredOutputValidationError
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubOperationError,
    GitOperationError,
    RoadmapStageError,
    ToolExecutionError,
)
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import failure as failure_module
from devops_cli.roadmap.failure import (
    ACTION_BY_CLASS,
    FailureAction,
    FailureClass,
    FailureEvidence,
    action_for,
    classify_failure,
    failure_lines,
    left_action,
)
from devops_cli.roadmap.implement.implement_step import commands_failure
from devops_cli.roadmap.stage.stage import (
    StageApplied,
    StagedChange,
    StagePlan,
    StageResult,
    StageTarget,
    stage_results,
)
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_verify import Finding
from devops_cli.roadmap.stores.store import Item
from tests.support.builders import make_stage_proposal
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import make_checkout

TEXTS = MESSAGES.roadmap

# #2175, the stop comment of group 2: the check `mypy --strict` failed on a test file.
EXCERPT_2175 = (
    "uv run mypy --strict -- test_get_ollama_semaphore.py exited with status 1.\n"
    'test_get_ollama_semaphore.py:5: error: Skipping analyzing "devops_cli.ai.client.unified": '
    "module is installed, but missing library stubs or py.typed marker  [import-untyped]\n"
    "test_get_ollama_semaphore.py:9: error: Function is missing a return type annotation  "
    "[no-untyped-def]\n"
    "Found 2 errors in 1 file (checked 1 source file)"
)
# #2735, the stop comment of group 1: the tool `edit_file` came back as a retry six times.
EXCERPT_2735 = (
    "UnexpectedModelBehavior: Tool 'edit_file' exceeded max retries count of 5. Consider raising "
    "the retry limit, or see the docs on tool retries: "
    "https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/#tool-retries\n"
    "Refused commands: 0. Other retries: 6."
)
# #2747, the stop comment of group 1: Ollama could not parse the call of the model.
EXCERPT_2747 = (
    "ModelHTTPError: HTTP 400, model devops-coder, body: litellm.BadRequestError: "
    "Ollama_chatException - KeyError: <text>, Got unexpected response from Ollama: "
    "{<text>: <text>}\nRefused commands: cd 2, python 1. Other retries: 0."
)
# #3484, the docs step in a target repository: the installed copy of the command wrote outside the
# worktree, to a path that the Job mounts read-only.
EXCERPT_3484 = (
    "uv run devops docs generate --sync-readme exited with status 1.\n"
    "OSError: [Errno 30] Read-only file system: '/app/docs'"
)
# #2924, the review notes of the pull request: ten tests failed on the base.
EXCERPT_2924 = (
    "Fail-to-pass run (`uv run devops ci fail-to-pass --base origin/main`): 10 tests failed on "
    "the base and pass now"
)


REAL = [
    pytest.param(FailureEvidence(text=EXCERPT_2175), FailureClass.TYPES, id="2175-mypy"),
    pytest.param(
        FailureEvidence(text=EXCERPT_2735), FailureClass.REFUSED_TOOL, id="2735-tool-retries"
    ),
    pytest.param(FailureEvidence(text=EXCERPT_2747), FailureClass.PARSER, id="2747-ollama-parser"),
    pytest.param(FailureEvidence(text=EXCERPT_2924), FailureClass.TEST, id="2924-tests-failed"),
]

FROM_THE_JOB = [
    pytest.param(
        FailureEvidence(text="ModelHTTPError: HTTP 503, model devops-coder, body: unavailable"),
        FailureClass.PROVIDER,
        id="provider-503",
    ),
    pytest.param(
        FailureEvidence(text="ModelHTTPError: HTTP 429, model devops-coder, rate limit"),
        FailureClass.PROVIDER,
        id="provider-429",
    ),
    pytest.param(
        FailureEvidence(text="APIConnectionError: Connection error."),
        FailureClass.PROVIDER,
        id="provider-connection",
    ),
    pytest.param(
        FailureEvidence(
            text=TEXTS.implement_stop_program_failed.format(
                command="uv run pytest", status=1, output="FAILED tests/test_x.py::test_y"
            )
        ),
        FailureClass.TEST,
        id="test-pytest",
    ),
    pytest.param(
        FailureEvidence(text="ruff-check....Failed\nE501 Line too long"),
        FailureClass.LINT,
        id="lint-ruff",
    ),
    pytest.param(
        FailureEvidence(
            text=TEXTS.implement_stop_hooks_failed.format(stage="pre-push", status=1, output="")
        ),
        FailureClass.LINT,
        id="lint-hooks",
    ),
    pytest.param(
        FailureEvidence(
            text=TEXTS.implement_over_window.format(
                measured=9000, limit=6000, window=8000, reserve=2000
            )
        ),
        FailureClass.PLAN_DEFECT,
        id="plan-inputs-over-the-window",
    ),
    pytest.param(
        FailureEvidence(text="Task group 2, Route the stage row, has a task that is not ticked."),
        FailureClass.PLAN_DEFECT,
        id="plan-unticked-group",
    ),
    pytest.param(
        FailureEvidence(text=TEXTS.stage_ready_needs_fix.format(pull=5)),
        FailureClass.PLAN_DEFECT,
        id="plan-open-finding",
    ),
    pytest.param(
        FailureEvidence(text="The function is already deleted in the current codebase."),
        FailureClass.PREMISE_FALSE,
        id="premise-already-deleted",
    ),
    pytest.param(
        FailureEvidence(text="The premise is false: the flag does not exist."),
        FailureClass.PREMISE_FALSE,
        id="premise-said",
    ),
    pytest.param(FailureEvidence(exit_status=137), FailureClass.OOM, id="oom-exit-status"),
    pytest.param(
        FailureEvidence(text="The container was OOMKilled."), FailureClass.OOM, id="oom-text"
    ),
    pytest.param(
        FailureEvidence(
            text=TEXTS.implement_stop_program_failed.format(
                command="uv run pytest", status=137, output=""
            ),
        ),
        FailureClass.OOM,
        id="oom-command-killed",
    ),
    pytest.param(FailureEvidence(exit_status=124), FailureClass.TIMEOUT, id="timeout-exit-status"),
    pytest.param(
        FailureEvidence(
            text=TEXTS.implement_stop_program_timeout.format(command="uv run pytest", seconds=900)
        ),
        FailureClass.TIMEOUT,
        id="timeout-command",
    ),
    pytest.param(
        FailureEvidence(text=TEXTS.implement_stop_checks_timeout.format(seconds=3600)),
        FailureClass.TIMEOUT,
        id="timeout-checks",
    ),
    pytest.param(
        FailureEvidence(refusal="Command 'curl' is not allowed."),
        FailureClass.REFUSED_TOOL,
        id="refused-tool",
    ),
    pytest.param(
        FailureEvidence(text="Refused commands: cd 2. Other retries: 0."),
        FailureClass.REFUSED_TOOL,
        id="refused-commands",
    ),
    pytest.param(
        FailureEvidence(text=TEXTS.implement_stop_conflict),
        FailureClass.CONFLICT,
        id="conflict-pull-request",
    ),
    pytest.param(
        FailureEvidence(text=TEXTS.implement_stop_rebase.format(branch="main", output="CONFLICT")),
        FailureClass.CONFLICT,
        id="conflict-rebase",
    ),
    pytest.param(
        FailureEvidence(text=TEXTS.implement_stop_checks_unread),
        FailureClass.CI_INFRA,
        id="infra-checks-unread",
    ),
    pytest.param(
        FailureEvidence(text="The check Static Analysis failed.", check="Static Analysis"),
        FailureClass.LINT,
        id="check-name-static",
    ),
    pytest.param(
        FailureEvidence(text="The check Tests & Coverage failed.", check="Tests & Coverage"),
        FailureClass.TEST,
        id="check-name-tests",
    ),
    pytest.param(
        FailureEvidence(text="The check Test Job Duration failed.", check="Test Job Duration"),
        FailureClass.CI_INFRA,
        id="check-name-duration-is-no-test",
    ),
    pytest.param(
        FailureEvidence(text="The check Service Image failed.", check="Service Image"),
        FailureClass.CI_INFRA,
        id="check-name-image",
    ),
    pytest.param(FailureEvidence(), FailureClass.CI_INFRA, id="nothing-is-ci-infra"),
    pytest.param(
        FailureEvidence(text="Something that no rule knows."),
        FailureClass.CI_INFRA,
        id="unknown-is-ci-infra",
    ),
]


@pytest.mark.parametrize(("evidence", "expected"), [*REAL, *FROM_THE_JOB])
def test_the_classifier_maps_each_excerpt_to_its_class(
    evidence: FailureEvidence, expected: FailureClass
) -> None:
    assert classify_failure(evidence) is expected


# A stop of the job whose cause has no class from its site: the reason, the expected class, the
# check and the log of the check. The stop texts are synthetic: the stop comments of the window of
# #3476 hold the task text and the agent text of other items, so they are no fixture. Each case
# follows a pattern that the issue counts, with the messages of the job as they read now. The five
# classes that a site sets are not here: the classifier does not return them.
CLAIM = (
    "I have successfully completed the task. The item is already implemented and all acceptance "
    "criteria are met."
)


def _scoped(name: str, command: str, output: str) -> str:
    """The reason of a scoped check that still failed after the fix rounds."""
    return TEXTS.implement_stop_scoped_failed.format(
        name=name, rounds=3, command=command, output=output
    )


class Stop(NamedTuple):
    reason: str
    expected: FailureClass
    check: str = ""
    log: str = ""
    exit_status: int | None = None


STOPS = [
    pytest.param(
        Stop(
            _scoped(
                "pre-push", "uv run pre-commit run", "ruff-check....Failed\nE501 Line too long"
            ),
            FailureClass.LINT,
            check="pre-push",
            log="ruff-check....Failed\nE501 Line too long",
        ),
        id="scoped-check-lint",
    ),
    pytest.param(
        Stop(
            _scoped(
                "static", "uv run devops ci --check --only types", "a.py:3: error: bad  [misc]"
            ),
            FailureClass.TYPES,
            check="static",
            log="uv run mypy --strict a.py\na.py:3: error: bad  [misc]",
        ),
        id="scoped-check-types",
    ),
    pytest.param(
        Stop(
            _scoped(
                "tests", "uv run devops ci test tests/test_x.py", "FAILED tests/test_x.py::test_y"
            ),
            FailureClass.TEST,
            check="tests",
            log="FAILED tests/test_x.py::test_y - AssertionError\n1 failed, 3 passed",
        ),
        id="scoped-check-test",
    ),
    pytest.param(
        Stop(
            "",
            FailureClass.TEST,
            check="Tests & Coverage",
            log="FAILED tests/test_x.py::test_y\n1 failed",
        ),
        id="scoped-log-decides-with-no-reason",
    ),
    pytest.param(
        Stop(
            TEXTS.implement_stop_command_failed.format(
                command="uv run mypy --strict a.py", status=1, output="a.py:1: error: x  [misc]"
            ),
            FailureClass.TYPES,
        ),
        id="verification-command-types",
    ),
    pytest.param(
        Stop(
            TEXTS.implement_stop_command_refused.format(command="curl x", reason="not allowed"),
            FailureClass.REFUSED_TOOL,
        ),
        id="verification-command-refused",
    ),
    pytest.param(Stop(EXCERPT_2735, FailureClass.REFUSED_TOOL), id="tool-retries-exceeded"),
    pytest.param(Stop(EXCERPT_2747, FailureClass.PARSER), id="ollama-parser"),
    pytest.param(
        Stop("ModelHTTPError: HTTP 503, model m, body: unavailable", FailureClass.PROVIDER),
        id="provider-503",
    ),
    pytest.param(
        Stop(
            "ModelHTTPError: HTTP 503, model m",
            FailureClass.PROVIDER,
            check="Tests & Coverage",
            log="FAILED tests/test_x.py::test_y",
        ),
        id="a-provider-error-in-a-fix-step-beats-the-log-of-the-check",
    ),
    pytest.param(
        Stop(
            TEXTS.implement_stop_program_failed.format(command="uv run x", status=137, output=""),
            FailureClass.OOM,
            exit_status=137,
        ),
        id="command-killed",
    ),
    pytest.param(
        Stop(
            TEXTS.implement_stop_program_timeout.format(command="uv run x", seconds=900),
            FailureClass.TIMEOUT,
        ),
        id="command-timeout",
    ),
    pytest.param(
        Stop(
            TEXTS.implement_stop_rebase.format(branch="main", output="CONFLICT (content)"),
            FailureClass.CONFLICT,
        ),
        id="rebase-conflict",
    ),
    pytest.param(
        Stop(TEXTS.implement_stop_checks_unread, FailureClass.CI_INFRA),
        id="checks-unread",
    ),
    pytest.param(
        Stop(TEXTS.implement_stop_no_change, FailureClass.CI_INFRA),
        id="a-no-change-reason-alone-is-ci-infra",
    ),
]


def _class_of_stop(stop: Stop) -> FailureClass:
    return classify_failure(
        FailureEvidence(
            text=stop.reason, exit_status=stop.exit_status, check=stop.check, log=stop.log
        )
    )


@pytest.mark.parametrize("stop", STOPS)
def test_each_synthetic_stop_text_has_its_class(stop: Stop) -> None:
    assert _class_of_stop(stop) is stop.expected


def test_the_words_already_implemented_do_not_give_premise_false() -> None:
    """The claim of the agent is no evidence (#2116): the evidence has no field for it, and the
    reason of a fix step that changed no file is not read for it."""
    assert "agent" not in FailureEvidence._fields
    assert classify_failure(FailureEvidence(text=TEXTS.implement_stop_no_change)) is (
        FailureClass.CI_INFRA
    )
    assert classify_failure(FailureEvidence(text=f"{CLAIM}\n{EXCERPT_2175}")) is FailureClass.TYPES


# The classes that a site of the step sets and the classifier never returns. The tests of the step
# (test_roadmap_implement_step_failure_class.py and the job tests) run each site.
TYPED_BY_SITE = {
    FailureClass.NO_CHANGE_IN_FIX,
    FailureClass.TESTS_LOST,
    FailureClass.HEAD_MOVED,
    FailureClass.OUTPUT_CAP,
    FailureClass.LIMIT_REACHED,
    FailureClass.OUTSIDE_PLAN,
}


def test_the_classifier_never_returns_a_class_that_a_site_sets() -> None:
    from_classifier = {case.values[1] for case in [*REAL, *FROM_THE_JOB]}
    from_stops = {case.values[0].expected for case in STOPS}
    assert not (from_classifier | from_stops) & TYPED_BY_SITE
    assert from_classifier | from_stops | TYPED_BY_SITE | {FailureClass.READ_ONLY_PATH} == set(
        FailureClass
    )


@pytest.mark.parametrize(
    "text",
    [
        EXCERPT_3484,
        "OSError: [Errno 30] Read-only file system: '/app/docs'",
        "git: error: unable to write the file: EROFS",
    ],
)
def test_a_write_to_a_read_only_path_is_the_class_read_only_path_and_is_not_retried(
    text: str,
) -> None:
    klass = classify_failure(FailureEvidence(text=text))

    assert klass is FailureClass.READ_ONLY_PATH
    assert action_for(klass) is FailureAction.WAIT


def test_the_classifier_reads_the_log_of_the_check() -> None:
    assert classify_failure(FailureEvidence(log="ruff-check....Failed")) is FailureClass.LINT
    assert classify_failure(FailureEvidence(text="x", log="2 failed in 1s")) is FailureClass.TEST


def test_the_log_of_a_check_decides_no_cause_outside_the_code() -> None:
    """A test name with `timeout` in it is no timeout."""
    log = "FAILED tests/test_x.py::test_a_timed_out_call - AssertionError"

    assert classify_failure(FailureEvidence(check="tests", log=log)) is FailureClass.TEST


def test_the_classifier_is_pure_and_gives_the_same_class_for_the_same_evidence() -> None:
    evidence = FailureEvidence(text=EXCERPT_2747, exit_status=1, check="x")
    before = repr(evidence)

    assert [classify_failure(evidence) for _ in range(3)] == [FailureClass.PARSER] * 3
    assert repr(evidence) == before


def test_the_parser_wins_over_the_provider_for_the_http_error_of_ollama() -> None:
    assert classify_failure(FailureEvidence(text="ModelHTTPError: HTTP 400, body: x")) is (
        FailureClass.PROVIDER
    )
    assert classify_failure(FailureEvidence(text=EXCERPT_2747)) is FailureClass.PARSER


def test_a_signal_exit_status_beats_the_text() -> None:
    assert (
        classify_failure(FailureEvidence(text="ruff failed", exit_status=137)) is FailureClass.OOM
    )
    assert classify_failure(FailureEvidence(text="ruff failed", exit_status=1)) is FailureClass.LINT


def test_the_classes_are_the_nineteen_of_the_taxonomy() -> None:
    assert {klass.value for klass in FailureClass} == {
        "provider",
        "parser",
        "test",
        "lint",
        "types",
        "plan_defect",
        "premise_false",
        "oom",
        "timeout",
        "refused_tool",
        "conflict",
        "ci_infra",
        "no_change_in_fix",
        "tests_lost",
        "head_moved",
        "output_cap",
        "read_only_path",
        "limit_reached",
        "outside_plan",
    }


def test_each_class_has_exactly_one_default_action_in_one_table() -> None:
    assert set(ACTION_BY_CLASS) == set(FailureClass)
    assert all(isinstance(action, FailureAction) for action in ACTION_BY_CLASS.values())


def test_the_default_actions_are_the_ones_of_the_design() -> None:
    assert {klass.value: action.value for klass, action in ACTION_BY_CLASS.items()} == {
        "provider": "retry",
        "parser": "change_tier",
        "test": "repair",
        "lint": "repair",
        "types": "repair",
        "plan_defect": "amend",
        "premise_false": "return",
        "oom": "raise_limit",
        "timeout": "retry",
        "refused_tool": "wait",
        "conflict": "wait",
        "ci_infra": "retry",
        "no_change_in_fix": "wait",
        "tests_lost": "wait",
        "head_moved": "retry",
        "output_cap": "raise_limit",
        "read_only_path": "wait",
        "limit_reached": "raise_limit",
        "outside_plan": "wait",
    }


def test_the_table_cannot_be_changed_at_run_time() -> None:
    with pytest.raises(TypeError, match="does not support item assignment"):
        ACTION_BY_CLASS[FailureClass.OOM] = FailureAction.RETRY  # type: ignore[index]


def test_every_action_has_a_text_for_the_comment() -> None:
    assert set(TEXTS.implement_failure_action_text) == {action.value for action in FailureAction}


def test_the_action_left_is_the_default_unless_the_job_took_it_already() -> None:
    assert action_for(FailureClass.OOM) is FailureAction.RAISE_LIMIT
    assert left_action(FailureClass.OOM, None) is FailureAction.RAISE_LIMIT
    assert left_action(FailureClass.TYPES, None) is FailureAction.REPAIR
    assert left_action(FailureClass.TYPES, FailureAction.REPAIR) is FailureAction.WAIT
    assert left_action(FailureClass.CONFLICT, None) is FailureAction.WAIT


def test_the_lines_of_a_stop_name_the_class_the_action_taken_and_the_action_left() -> None:
    plain = failure_lines(FailureClass.PARSER)
    repaired = failure_lines(FailureClass.TEST, repair_rounds=3)

    assert plain.splitlines() == [
        "Failure class: `parser`.",
        "Action taken: none.",
        "Action left: `change_tier`: run the item with a stronger model tier.",
    ]
    assert repaired.splitlines() == [
        "Failure class: `test`.",
        "Action taken: `repair`, 3 fix round(s).",
        "Action left: `wait`: wait for a person.",
    ]


def test_a_tier_change_that_did_not_work_is_taken_and_leaves_wait() -> None:
    """A parser failure that moved the step to another tier took `change_tier` (#3060)."""
    moved = failure_lines(FailureClass.PARSER, tier_changes=1)

    assert left_action(FailureClass.PARSER, FailureAction.CHANGE_TIER) is FailureAction.WAIT
    assert moved.splitlines() == [
        "Failure class: `parser`.",
        "Action taken: `change_tier`, 1 tier move(s).",
        "Action left: `wait`: wait for a person.",
    ]


def test_failure_lines_names_amend_taken_and_wait_left() -> None:
    lines = failure_lines(FailureClass.PLAN_DEFECT, taken=FailureAction.AMEND)
    assert lines.splitlines() == [
        "Failure class: `plan_defect`.",
        "Action taken: `amend`.",
        "Action left: `wait`: wait for a person.",
    ]


# ── A refused verification command is a refused tool (#3263) ──────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "curl http://example.com",
        "curl",
        "python",
        "rg",
        "docker buildx build .",
        "uv run 'devops",
        "! git grep -O name src/",
        "! git grep -n name src/ | cat",
        "! git grep -n name",
        "grep -n zz " + "a" * 3000,
    ],
    ids=[
        "program",
        "one-word",
        "python",
        "rg",
        "multi-word",
        "unparsed",
        "option",
        "shape-pipe",
        "no-path",
        "too-long",
    ],
)
def test_a_refused_verification_command_is_a_refused_tool_that_waits_for_a_person(
    tmp_path: Path, implement_programs: ProcessFake, command: str
) -> None:
    """The text lists `mypy` and `ruff` among the allowed programs, and the rules for a type check
    read that word. The rule for a refused command comes first, from the text of the message."""
    reason = commands_failure(make_checkout(tmp_path), [command])

    assert reason is not None
    klass = classify_failure(FailureEvidence(text=reason))
    assert (klass, action_for(klass)) == (FailureClass.REFUSED_TOOL, FailureAction.WAIT)


def test_the_rule_for_a_refused_command_is_the_message_of_the_step() -> None:
    reason = TEXTS.implement_stop_command_refused.format(command="x y", reason="mypy is a word")

    assert classify_failure(FailureEvidence(text=reason)) is FailureClass.REFUSED_TOOL


def test_a_verification_command_that_ran_and_failed_is_not_a_refused_tool() -> None:
    reason = TEXTS.implement_stop_command_failed.format(
        command="uv run mypy --strict -- a.py", status=1, output="a.py:1: error: x  [misc]"
    )

    assert classify_failure(FailureEvidence(text=reason)) is FailureClass.TYPES


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest tests/roadmap/test_rate_limit.py",
        "! git grep -n 'timed out' src/ -x",
        "! git grep -n x src/ -k 'out of memory'",
        "! git grep -n x src/ -k 'merge conflict'",
        "! git grep -n x src/ -k JSONDecodeError",
        "curl https://example.com/ModelHTTPError",
    ],
    ids=["rate-limit", "timed-out", "out-of-memory", "merge-conflict", "parser", "provider"],
)
def test_a_word_of_a_refused_command_does_not_change_its_class(
    tmp_path: Path, implement_programs: ProcessFake, command: str
) -> None:
    """The echoed command can hold the words of any other rule, so the rule for a refused command
    is read first, at the start of the text."""
    reason = commands_failure(make_checkout(tmp_path), [command])

    assert reason is not None
    klass = classify_failure(FailureEvidence(text=reason))
    assert (klass, action_for(klass)) == (FailureClass.REFUSED_TOOL, FailureAction.WAIT)


def test_a_refused_command_inside_a_longer_text_is_not_the_rule_for_a_refused_command() -> None:
    inner = TEXTS.implement_stop_command_refused.format(command="x", reason="y")

    assert classify_failure(FailureEvidence(text=f"timed out\n{inner}")) is FailureClass.TIMEOUT


def test_a_staged_item_with_an_open_finding_is_a_failed_attempt_not_a_staged_plan() -> None:
    item = Item(
        number=1, title="fix(roadmap): the job drops a comment", url="https://example.com/1"
    )
    open_finding = Finding(
        type=DefectType.OTHER,
        where="tasks.md",
        problem="The task group says placeholder.",
        quote="placeholder",
    )
    change = StagedChange(
        target=StageTarget(item, "fix", "the-job-drops-a-comment"),
        title="docs(openspec): plan #1",
        body="Plans #1",
        files={},
        groups=(),
        validated=True,
        budget=1000,
        proposal=make_stage_proposal(),
        open_findings=(open_finding,),
    )

    results = stage_results(
        StagePlan(repo="example/roadmap", ready=(change,)), StageApplied(staged=(1,))
    )

    assert results == {1: StageResult.FAILED}


class _CustomAIError(AIClientError):
    """A subclass that the table has no entry for."""


class _CustomGitError(GitOperationError):
    """A subclass that the table has no entry for."""


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (RoadmapItemChangedError("the item changed"), FailureClass.HEAD_MOVED),
        (StructuredOutputValidationError("no schema fits"), FailureClass.PARSER),
        (AIClientError("the provider is down"), FailureClass.PROVIDER),
        (RoadmapStageError("a plan broke a rule"), FailureClass.PLAN_DEFECT),
        (GitHubOperationError("the write failed"), FailureClass.CI_INFRA),
        (GitOperationError("the push failed"), FailureClass.CI_INFRA),
        (ToolExecutionError("the tool failed"), FailureClass.CI_INFRA),
        (DevOpsCLIError("any other error"), FailureClass.CI_INFRA),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, Exception) else value.value,
)
def test_class_by_exception_gives_each_mapped_exception_its_class(
    exc: DevOpsCLIError, expected: FailureClass
) -> None:
    assert failure_module.failure_class_of(exc) is expected


def test_class_by_exception_puts_a_type_before_each_parent_it_is_a_subclass_of() -> None:
    types = [exception_type for exception_type, _ in failure_module.CLASS_BY_EXCEPTION]

    for index, exception_type in enumerate(types):
        assert not any(
            issubclass(types[later], exception_type) for later in range(index + 1, len(types))
        )


def test_class_by_exception_ends_with_the_base_error_so_that_every_error_has_a_class() -> None:
    last_type, last_class = failure_module.CLASS_BY_EXCEPTION[-1]

    assert (last_type, last_class) == (DevOpsCLIError, FailureClass.CI_INFRA)


def test_class_by_exception_gives_a_subclass_with_no_entry_the_class_of_its_parent() -> None:
    assert (
        failure_module.failure_class_of(_CustomAIError("custom")),
        failure_module.failure_class_of(_CustomGitError("custom")),
    ) == (FailureClass.PROVIDER, FailureClass.CI_INFRA)


def test_class_by_exception_uses_only_classes_of_the_taxonomy_and_each_type_once() -> None:
    types = [exception_type for exception_type, _ in failure_module.CLASS_BY_EXCEPTION]

    assert (len(types), len(set(types))) == (len(types), len(types))
    assert {klass for _, klass in failure_module.CLASS_BY_EXCEPTION} <= set(FailureClass)


def test_step_name_holds_the_plan_and_the_apply_step() -> None:
    assert [step.value for step in failure_module.StepName] == ["plan", "apply"]


def test_step_name_values_are_unique_one_word_strings() -> None:
    values = [step.value for step in failure_module.StepName]

    assert len(values) == len(set(values))
    assert all(value.isalpha() and value == value.lower() for value in values)
