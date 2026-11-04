"""Every numeric limit of the roadmap jobs has a class, and the limits fit the windows (#3206).

The jobs carry limits in `config/constants.py` (`CONST_ROADMAP_*`) and `config/defaults.py`
(`DEFAULT_ROADMAP_*`). A limit cuts work, so each one is in the table below with the decision that
was made about it and the reason. The test fails when a limit is added with no entry, and when an
entry names a limit that no longer exists, so the table stays in step with the code.

The classes:

- `raised`: a cap that cut work short and now sits far above the old value.
- `guard`: the loop guard of a job, a high count of requests or tool calls that ends a model that
  loops before the Job deadline does. It is raised a lot and not removed.
- `window`: a share of the context window of the task, or a number that must fit the window.
- `setting`: a number that a person tunes, so it is a setting with a variable and a default.
- `kept`: a limit that an outside system sets, or a size that protects a person, a log, the memory
  or the secret masking. The reason says which.
- `other`: a schedule, an identifier or a policy value that no run is cut by.
"""

from __future__ import annotations

from typing import Final

import pytest
import yaml

from devops_cli.config import constants, defaults
from devops_cli.config.defaults import (
    DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW,
    DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_ROADMAP_STAGE_STEP_TOKENS,
)
from devops_cli.roadmap.implement_step import output_cap
from tests.support.paths import REPO_ROOT

CLASSES: Final = frozenset({"raised", "guard", "window", "setting", "kept", "other"})

# Constants that the change took out. A test holds that none comes back.
REMOVED: Final[tuple[str, ...]] = (
    # The output tokens of a stage run are in its messages, which the window holds.
    "CONST_ROADMAP_STAGE_MAX_OUTPUT_TOKENS",
    # The output cap of a reply is a share of the window: `CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE`.
    "CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS",
    # The three time limits are settings: `DEFAULT_ROADMAP_IMPLEMENT_*_TIMEOUT_SECONDS`.
    "CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS",
    "CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS",
    "CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS",
)

LIMITS: Final[dict[str, tuple[str, str]]] = {
    # ── Refine investigation ──────────────────────────────────────────────────────────────
    "CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS": (
        "guard",
        "was 12; the window ends the run first",
    ),
    "CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS": (
        "guard",
        "was 20; the window ends the run first",
    ),
    "CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS": (
        "kept",
        "the calls one turn can make; sets when the tools go",
    ),
    "CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES": (
        "kept",
        "retries for a reply that breaks the schema; a stuck model fails again",
    ),
    "CONST_ROADMAP_REFINE_TOOL_MAX_LINES": (
        "raised",
        "was 120; a tool answer, bounded by the window",
    ),
    "CONST_ROADMAP_REFINE_TOOL_MAX_CHARS": (
        "raised",
        "was 4000; a tool answer, bounded by the window",
    ),
    "CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE": (
        "window",
        "the share of the window kept for the reply",
    ),
    "CONST_ROADMAP_INVESTIGATION_MAX_BLOB_BYTES": ("kept", "the memory of one tool answer"),
    "CONST_ROADMAP_REFINE_MAX_BODY_CHARS": (
        "kept",
        "GitHub: an issue body holds 65,536 characters",
    ),
    "CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES": ("raised", "was 3; web searches of one item"),
    "CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY": (
        "kept",
        "the size of the answer of one search; the cap on characters bounds it",
    ),
    "CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL": (
        "kept",
        "paths in the context; the context says how many it left out, and the tools read the rest",
    ),
    "CONST_ROADMAP_REFINE_MAX_SPECS": ("raised", "was 5; specs named in the context"),
    "CONST_ROADMAP_REFINE_MAX_REQUIREMENTS_PER_SPEC": (
        "raised",
        "was 40; requirement names that a plan needs for MODIFIED",
    ),
    "CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM": (
        "kept",
        "stops a loop of replies between refine and another bot",
    ),
    "CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS": ("kept", "the period of the cap above"),
    "CONST_ROADMAP_REFINE_MAX_REPLIES": ("raised", "was 5; replies of people that reach the model"),
    "CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS": ("raised", "was 1024; one reply of a person"),
    "CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS": ("kept", "bounds the GitHub reads of each round"),
    # ── Stage ─────────────────────────────────────────────────────────────────────────────
    "CONST_ROADMAP_STAGE_TOOL_MAX_CALLS": ("guard", "was 30; the window ends the run first"),
    "CONST_ROADMAP_STAGE_MAX_REQUESTS": ("guard", "was 40; the window ends the run first"),
    "CONST_ROADMAP_STAGE_LOG_MAX_COUNT": ("raised", "was 20; commits of one `git_log` answer"),
    "CONST_ROADMAP_STAGE_MAP_MAX_FILES": ("raised", "was 20; files of one `repo_map` answer"),
    "CONST_ROADMAP_STAGE_MAP_LINE_CHARS": (
        "kept",
        "one line of the map; the lines of the map fit one tool answer",
    ),
    "CONST_ROADMAP_STAGE_SPEC_MAX_CHARS": ("raised", "was 8000; one `read_spec` answer"),
    "CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS": (
        "window",
        "context of the first plan request; fixed, so a larger window gives no larger request",
    ),
    "CONST_ROADMAP_STAGE_BODY_MAX_TOKENS": (
        "window",
        "body of the item in the first plan request; fixed, as the context cap is",
    ),
    "CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS": (
        "window",
        "room that the first plan request leaves below the limit of the tools for their answers",
    ),
    "CONST_ROADMAP_STAGE_REFERENCE_NAME_MAX_CHARS": (
        "kept",
        "the text `references` searches for; a name is short, and a longer text is no name",
    ),
    "CONST_ROADMAP_STAGE_REFERENCE_MAX_FILES": (
        "kept",
        "files of one `references` answer; the answer says how many it left out",
    ),
    "CONST_ROADMAP_STAGE_REFERENCE_LINES_PER_FILE": (
        "kept",
        "line numbers shown for a file; the count of the file is exact",
    ),
    "CONST_ROADMAP_STAGE_ISSUE_BODY_CHARS": (
        "kept",
        "GitHub text in one `read_issue` answer; the tool cuts data it did not write",
    ),
    "CONST_ROADMAP_STAGE_ISSUE_COMMENTS": ("kept", "comments of one `read_issue` answer"),
    "CONST_ROADMAP_STAGE_ISSUE_COMMENT_CHARS": (
        "kept",
        "GitHub text in one comment of a `read_issue` answer",
    ),
    "CONST_ROADMAP_STAGE_ISSUE_TITLE_CHARS": (
        "kept",
        "GitHub text in one title or label of a tool answer",
    ),
    "CONST_ROADMAP_STAGE_FIND_MAX_RESULTS": (
        "kept",
        "items of one `find_issues` answer; one request to the search of GitHub",
    ),
    "CONST_ROADMAP_STAGE_FIND_TERMS_MAX_CHARS": (
        "kept",
        "the terms of one search; the search of GitHub reads a short query",
    ),
    "CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS": (
        "kept",
        "git commands of one premise probe; the probe runs in the process of the job",
    ),
    "CONST_ROADMAP_STAGE_PROBE_DEFINITION_LINES": ("kept", "lines of definition the probe shows"),
    "CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS": (
        "kept",
        "the verification slot sets no window: its default of 32,768 tokens is already under the 51,000 tokens that the three caps give",
    ),
    "CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS": ("kept", "same reason as the body cap"),
    "CONST_ROADMAP_STAGE_VERIFY_MAX_FILES": ("kept", "same reason as the body cap"),
    "DEFAULT_ROADMAP_STAGE_STEP_TOKENS": ("window", "was 40,000; half of the implement window"),
    "DEFAULT_ROADMAP_STAGE_LIMIT": ("setting", "items of one stage round; already a setting"),
    # ── Alternatives ──────────────────────────────────────────────────────────────────────
    "CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES": ("raised", "was 3; web searches of one item"),
    "CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS": (
        "raised",
        "was 6; PyPI and GitHub reads of one item",
    ),
    "CONST_ROADMAP_ALTERNATIVES_SEARCH_RESULTS": ("kept", "the size of the answer of one search"),
    "CONST_ROADMAP_ALTERNATIVES_MAX_BODY_TOKENS": (
        "raised",
        "was 4096; a quarter of the planner window",
    ),
    "CONST_ROADMAP_ALTERNATIVES_MAX_LICENSE_CHARS": (
        "kept",
        "a rule that tells a license name from a license text",
    ),
    "CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS": (
        "other",
        "the policy that says a tool is maintained",
    ),
    "DEFAULT_ROADMAP_ALTERNATIVES_LIMIT": ("kept", "items of one round"),
    "DEFAULT_ROADMAP_ALTERNATIVES_FIRST_PASS_LIMIT": (
        "setting",
        "items of one round while an item has no check",
    ),
    "DEFAULT_ROADMAP_ALTERNATIVES_RECHECK_DAYS": ("other", "the age at which a check is old"),
    "DEFAULT_ROADMAP_ALTERNATIVES_RETRY_DAYS": (
        "other",
        "the wait before a failed check is tried again",
    ),
    "DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES": ("other", "a schedule"),
    # ── Implement ─────────────────────────────────────────────────────────────────────────
    "CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS": (
        "guard",
        "was 80; the Job deadline is the only other stop of a looping model",
    ),
    "CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS": (
        "guard",
        "was 240; the Job deadline is the only other stop of a looping model",
    ),
    "CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS": (
        "raised",
        "was 16,000; one tool result, a twelfth of the window",
    ),
    "CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES": (
        "kept",
        "refusals in a row before the run ends; a model that repeats a refused call is stuck",
    ),
    "CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS": (
        "kept",
        "resends of a request that the provider failed with the status 400",
    ),
    "CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS": (
        "window",
        "the share of the window that the inputs leave to the turns",
    ),
    "CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE": (
        "window",
        "the output cap of a reply is the window divided by this",
    ),
    "CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS": ("raised", "was 3000; a sixteenth of the window"),
    "CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES": (
        "kept",
        "lines of command output in a stop report",
    ),
    "CONST_ROADMAP_IMPLEMENT_LOG_CHARS": (
        "raised",
        "was 6000; the log of a failed check for the fix step",
    ),
    "CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS": (
        "kept",
        "the rule of the project: a pull request body holds 1,000 characters",
    ),
    "CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS": (
        "kept",
        "GitHub comment of 65,536 characters, read by a person",
    ),
    "CONST_ROADMAP_IMPLEMENT_DIFF_CHARS": (
        "kept",
        "GitHub comment of 65,536 characters, read by a person",
    ),
    "CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS": ("kept", "the secret masking is slower than linear"),
    "CONST_ROADMAP_IMPLEMENT_REASON_PATHS": ("kept", "paths in a stop reason, read by a person"),
    "CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS": (
        "kept",
        "the words of a verification command must fit one process argument list (E2BIG at about 128000)",
    ),
    "CONST_ROADMAP_IMPLEMENT_REASON_TESTS": ("kept", "tests in a stop reason, read by a person"),
    "CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS": (
        "kept",
        "GitHub comment of 65,536 characters, read by a person; the end of a log holds the failure",
    ),
    "CONST_ROADMAP_IMPLEMENT_REASON_CHARS": (
        "kept",
        "GitHub comment of 65,536 characters, read by a person",
    ),
    "CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS": (
        "kept",
        "fits the reason above with the line that names the stage",
    ),
    "CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES": (
        "kept",
        "bounds the run time of the scoped tests; the required checks of CI run the rest",
    ),
    "CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS": ("kept", "programs in a stop reason"),
    "CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS": ("kept", "the command that the Job log shows"),
    "CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS": ("kept", "the command that the Job log shows"),
    "CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_READ_CHARS": (
        "kept",
        "the secret masking is slower than linear",
    ),
    "CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS": ("kept", "a line of the Job log"),
    "CONST_ROADMAP_IMPLEMENT_STOP_REASONS": ("kept", "reasons in a stop, read by a person"),
    "CONST_ROADMAP_IMPLEMENT_TRACE_CHARS": (
        "kept",
        "the record in the issue body, read by a person",
    ),
    "CONST_ROADMAP_IMPLEMENT_TABLE_ROWS": (
        "kept",
        "GitHub comment of 65,536 characters, read by a person",
    ),
    "CONST_ROADMAP_IMPLEMENT_HEAD_POLLS": (
        "kept",
        "the time that GitHub takes to show a pushed head",
    ),
    "CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES": ("kept", "lines of the Job log in a comment"),
    "CONST_ROADMAP_IMPLEMENT_FIX_GROUP": ("other", "the number of the group of a fix step"),
    "DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS": (
        "setting",
        "was 600; under the router timeout of the gateway",
    ),
    "DEFAULT_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS": ("setting", "was 900"),
    "DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS": ("setting", "was 1800"),
    "DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS": (
        "setting",
        "was 2400; above the longest silent wait (the watch of 3600 s) by 600 s",
    ),
    "DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS": (
        "setting",
        "was 3600; above the stall by a row and a tick",
    ),
    "DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS": (
        "kept",
        "the cap of the admission policy of the Service's Jobs",
    ),
    "CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS": (
        "kept",
        "the cap of the admission policy of the Service's Jobs",
    ),
    "CONST_ROADMAP_IMPLEMENT_DEADLINE_LOG_LINES": (
        "kept",
        "the lines of the log whose digest shows progress",
    ),
    "DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS": (
        "setting",
        "already a setting; the repair turns of a step",
    ),
    "DEFAULT_ROADMAP_IMPLEMENT_DIGEST_CLEARS_PER_CLASS": (
        "setting",
        "already a setting; the clears by a new runner image for one class of stop",
    ),
    "DEFAULT_ROADMAP_IMPLEMENT_DIGEST_CLEARS_PER_ITEM": (
        "setting",
        "already a setting; the clears by a new runner image for one item",
    ),
    "CONST_ROADMAP_STOP_CLEAR_COMMENT_WINDOW_HOURS": (
        "kept",
        "the period of one comment of a clear by digest for an item",
    ),
    "DEFAULT_ROADMAP_IMPLEMENT_LIMIT": ("kept", "items of one round"),
    "DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS": ("kept", "the pace of the reads of GitHub"),
    "DEFAULT_ROADMAP_IMPLEMENT_INTERVAL_MINUTES": ("other", "a schedule"),
    # ── Shared by the jobs ────────────────────────────────────────────────────────────────
    "CONST_ROADMAP_RUN_ERROR_CHARS": ("kept", "the error text in a log and a reason"),
    "CONST_ROADMAP_RUN_ERROR_READ_CHARS": ("kept", "the secret masking is slower than linear"),
    "CONST_ROADMAP_RUN_TRACE_ARGUMENT_CHARS": ("kept", "the argument of a tool call in a trace"),
    "CONST_ROADMAP_EVAL_DETAIL_NAMES": ("kept", "names in the report of an eval"),
    "CONST_ROADMAP_EVAL_TASK_CHARS": ("kept", "the task text in the report of an eval"),
    "CONST_ROADMAP_EVAL_DETAIL_CHARS": ("kept", "the detail text in the report of an eval"),
    "CONST_ROADMAP_INBOX_CLAIM_DAYS": ("other", "the age at which a claim of an item ends"),
    "CONST_ROADMAP_INBOX_LABEL_NAMES": ("kept", "labels of an item in the inbox"),
    "DEFAULT_ROADMAP_INTAKE_SHORTLIST": (
        "kept",
        "candidates the model judges; sized with the embedding model of intake",
    ),
    "DEFAULT_ROADMAP_INTAKE_TEXT_CHARS": (
        "kept",
        "the text that intake embeds; sized with the embedding model",
    ),
    "DEFAULT_ROADMAP_INTAKE_EXCERPT_CHARS": (
        "kept",
        "the excerpt of a candidate that the model reads",
    ),
    "DEFAULT_ROADMAP_INTAKE_REASON_CHARS": ("kept", "the reason of a decision in a comment"),
    "DEFAULT_ROADMAP_INTAKE_LIMIT": ("kept", "candidates of one round"),
    "DEFAULT_ROADMAP_REFINE_LIMIT": ("kept", "items of one round"),
    "DEFAULT_ROADMAP_INTAKE_INTERVAL_MINUTES": ("other", "a schedule"),
    "DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES": ("other", "a schedule"),
    "DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES": ("other", "a schedule"),
    "DEFAULT_ROADMAP_STAGE_INTERVAL_MINUTES": ("other", "a schedule"),
    "DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES": ("other", "a schedule"),
    "CONST_ROADMAP_RELEASE_COMMENTS_WINDOW_HOURS": (
        "kept",
        "the releases that the first run of the release_comments row comments on",
    ),
    "CONST_ROADMAP_RELEASE_COMMENTS_LIST": ("kept", "the releases of one read"),
    "DEFAULT_ROADMAP_RELEASE_COMMENTS_INTERVAL_MINUTES": ("other", "a schedule"),
}

# The window of the planner in the example ConfigMap of the stack, which no raised cap passes.
PLANNER_WINDOW = yaml.safe_load(
    yaml.safe_load((REPO_ROOT / "k8s/devops/configmap.example.yaml").read_text(encoding="utf-8"))[
        "data"
    ]["devops-cli.yaml"]
)["ai"]["tasks"]["analysis"]["context_window"]


def _limits_in_code() -> set[str]:
    """The names of the numeric `CONST_ROADMAP_*` and `DEFAULT_ROADMAP_*` values."""
    found: set[str] = set()
    for module, prefix in ((constants, "CONST_ROADMAP_"), (defaults, "DEFAULT_ROADMAP_")):
        for name, value in vars(module).items():
            if (
                name.startswith(prefix)
                and isinstance(value, int | float)
                and not isinstance(value, bool)
            ):
                found.add(name)
    return found


def test_every_numeric_limit_of_the_roadmap_jobs_has_a_class() -> None:
    in_code = _limits_in_code()

    assert (sorted(in_code - set(LIMITS)), sorted(set(LIMITS) - in_code)) == ([], [])


def test_every_class_in_the_table_is_a_known_class_with_a_reason() -> None:
    assert [
        name for name, (klass, reason) in LIMITS.items() if klass not in CLASSES or not reason
    ] == []


@pytest.mark.parametrize("name", REMOVED)
def test_a_removed_limit_does_not_come_back(name: str) -> None:
    assert [module.__name__ for module in (constants, defaults) if name in vars(module)] == []


# ── The limits fit the windows ────────────────────────────────────────────────────────────


def test_the_inputs_of_a_step_and_the_reserve_of_its_turns_fit_the_implement_window() -> None:
    assert (
        DEFAULT_ROADMAP_STAGE_STEP_TOKENS + constants.CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
        <= DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW
    )


def test_a_packed_file_fits_the_budget_of_a_step_and_a_tool_result_a_share_of_the_window() -> None:
    window = DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW
    result_tokens = constants.CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS // 4

    assert (
        constants.CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS <= DEFAULT_ROADMAP_STAGE_STEP_TOKENS,
        result_tokens <= window // 8,
    ) == (True, True)


def test_the_output_cap_of_a_reply_leaves_the_inputs_of_a_step_in_the_window() -> None:
    window = DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW

    assert output_cap(window) + DEFAULT_ROADMAP_STAGE_STEP_TOKENS <= window


def test_a_reply_at_the_output_cap_ends_before_the_deadline_of_the_call() -> None:
    """The deadline is more than a cold read of the window (90 s) and a reply at the cap at the
    rate of the longest measured call (38 tokens per second)."""
    seconds = 90 + output_cap(DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW) / 38

    assert seconds < DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS


def test_the_body_of_an_item_in_the_alternatives_check_is_a_share_of_the_planner_window() -> None:
    assert constants.CONST_ROADMAP_ALTERNATIVES_MAX_BODY_TOKENS <= PLANNER_WINDOW // 4


def test_the_first_plan_request_and_its_reserve_fit_below_the_limit_of_the_tools() -> None:
    """Context, body and reserve, with 8,000 tokens for the prompts, the names of the capabilities
    and the other keys (the request counts about 34,000 tokens with the prompts, #3477)."""
    limit = (
        PLANNER_WINDOW - PLANNER_WINDOW // constants.CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE
    )

    assert (
        constants.CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS
        + constants.CONST_ROADMAP_STAGE_BODY_MAX_TOKENS
        + 8000
        + constants.CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS
        <= limit
    )


def test_the_lines_of_the_repo_map_fit_one_tool_answer() -> None:
    answer = constants.CONST_ROADMAP_REFINE_TOOL_MAX_CHARS

    assert (
        constants.CONST_ROADMAP_STAGE_MAP_MAX_FILES * constants.CONST_ROADMAP_STAGE_MAP_LINE_CHARS
        <= answer
    )


def test_the_texts_of_a_stop_fit_one_comment_of_65536_characters() -> None:
    comment = 65536
    parts = (
        constants.CONST_ROADMAP_IMPLEMENT_DIFF_CHARS
        + constants.CONST_ROADMAP_IMPLEMENT_REASON_CHARS
        + constants.CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS
        + constants.CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS
        + constants.CONST_ROADMAP_IMPLEMENT_TABLE_ROWS * 300
    )

    assert parts < comment


def test_the_body_of_a_refined_item_is_the_body_that_github_holds() -> None:
    assert constants.CONST_ROADMAP_REFINE_MAX_BODY_CHARS == 65536
