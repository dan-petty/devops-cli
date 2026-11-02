"""The failure taxonomy of the implement job (#3065): the classifier, and the table of default
actions.

The classifier is a pure function, so these tests give it text and read the class. The excerpts
marked with an issue number are real: they are the text of a stop comment, an agent message or a
pull request in that issue. The others are the messages that the job itself writes for the cause.
"""

from __future__ import annotations

import pytest

from devops_cli.lang import MESSAGES
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
# #2175, the last message of the agent at that stop.
AGENT_2175 = (
    "No actual code changes were needed since the method was already deleted - All items in "
    "task 2 are now marked as done in the tasks.md file"
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
# #2924, the review notes of the pull request: ten tests failed on the base.
EXCERPT_2924 = (
    "Fail-to-pass run (`uv run devops ci fail-to-pass --base origin/main`): 10 tests failed on "
    "the base and pass now"
)


REAL = [
    pytest.param(FailureEvidence(text=EXCERPT_2175), FailureClass.TYPES, id="2175-mypy"),
    pytest.param(
        FailureEvidence(text=EXCERPT_2175, agent=AGENT_2175),
        FailureClass.TYPES,
        id="2175-the-cause-of-the-stop-beats-the-claim-of-the-agent",
    ),
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
        FailureEvidence(text=TEXTS.implement_stop_no_change),
        FailureClass.PLAN_DEFECT,
        id="plan-no-change",
    ),
    pytest.param(
        FailureEvidence(text=TEXTS.implement_stop_unticked.format(task="2.1")),
        FailureClass.PLAN_DEFECT,
        id="plan-unticked",
    ),
    pytest.param(
        FailureEvidence(text=TEXTS.implement_stop_no_change, agent=AGENT_2175),
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


def test_the_table_test_covers_every_class() -> None:
    covered = {case.values[1] for case in [*REAL, *FROM_THE_JOB]}
    assert covered == set(FailureClass)


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


def test_the_classes_are_the_twelve_of_the_issue() -> None:
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
