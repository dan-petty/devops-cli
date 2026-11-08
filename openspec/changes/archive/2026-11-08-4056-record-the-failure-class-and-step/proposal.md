# Proposal

## Why

The issue #4056 reports that a failed stage item has no failure class and no step. The stage job records the Python class name of the error (`stage.failed_error`) and the time (`stage.failed_at`) in the job record of the item. `StageFailure` in `src/devops_cli/roadmap/stage/stage.py` holds the class name as a string, so the type of the exception is lost when `_failure_of` (plan) and `_write_failure` (write) build it. `devops roadmap explain` and `devops roadmap inbox` cannot show a class, and the issue #4060 cannot choose a retry time by class.

Only the implement job has a failure class today (`FailureClass` in `src/devops_cli/roadmap/failure.py`, #3065). Its classifier reads text and exit status. A stage error is an exception, so the class comes from the type of the exception.

## What Changes

- Add `StepName` to `src/devops_cli/roadmap/failure.py`: a `StrEnum` with the members `plan` and `apply`. Other issues add members when they use them.
- Add `CLASS_BY_EXCEPTION` to the same module: one tuple of (exception type, `FailureClass`), read with `isinstance`, most specific first:
  1. `RoadmapItemChangedError` gives `head_moved`.
  2. `StructuredOutputValidationError` gives `parser`.
  3. `AIClientError` gives `provider`.
  4. `RoadmapStageError` gives `plan_defect`.
  5. `GitHubOperationError`, `GitOperationError`, `ToolExecutionError` and `DevOpsCLIError` give `ci_infra`.
- Add the function `failure_class_of(exc)` to the same module. It returns the class of the first entry of the table that matches by `isinstance`. The two stage sites share it, so no site repeats the loop.
- Add the keys `stage.failed_step` and `stage.failed_class` to `StageRecordKey` in `src/devops_cli/roadmap/stores/store.py`.
- Add the fields `failure_class` and `step` to `StageFailure`. Both are required and keyword-only. `_failure_of` sets the step `plan`, and `_write_failure` sets the step `apply`. Both set the class with `failure_class_of`. The tests that build a `StageFailure` by hand pass the two fields.
- `_record_failures` writes the two keys in the same `set_marks` call as `stage.failed_at` and `stage.failed_error`, so the write costs no extra request. A staged item and an item stopped on the budget clear both keys with the other two.
- Fix the documents that the new keys make wrong: `docs/ROADMAP_WORKFLOW.md` (the table of keys), `docs/roadmap/stage.md` (the failure paragraph) and the docstrings of `StageRecordKey` and of the module `stage.py`.
- The change adds behavior that a consumer observes (the job record), so it carries a spec delta: two requirements in `roadmap-failure-taxonomy` and one in `roadmap-stage`.
- Not in this change: the retry time (#4060), a comment on the issue, and the output of `explain` and `inbox` (#3648).
- No setting is added, renamed, removed or tightened. `roadmap.stage.retry_hours` is unchanged. The example and the live ConfigMap need no change. The key-walk test of #4093 still proves that the example ConfigMap loads into `Settings`, and the PR comment says so.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-failure-taxonomy`: A failure has a class by its exception type, and a step
- `roadmap-stage`: A failed stage item records its failure class and step

## Impact

- Code: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stores/store.py`
- Tests: `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/stage/test_roadmap_stage_failure_class.py`, and the tests that build a `StageFailure` by hand: `tests/roadmap/stage/test_roadmap_stage_retry.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`
- Request cost: none added. The two keys go in the existing failure write.
- The consumer in this change is the writer `_record_failures`. The reader is the issue #4060. No `RETRY_AFTER` table is added, because nothing would read it.

## Feasibility

I checked the premise at `origin/main` (commit f16535fa) by reading the code and by running Python in the worktree.

- I ran the method resolution order of each mapped exception. `RoadmapItemChangedError` is a `GitHubOperationError`, which is a `DevOpsCLIError`. `StructuredOutputValidationError` is an `AIClientError`, which is an `LLMInferenceError`, which is a `DevOpsCLIError`. `RoadmapStageError`, `GitOperationError` and `ToolExecutionError` are direct children of `DevOpsCLIError`. `AIClientError` is not a `GitHubOperationError`, and `RoadmapStageError` is not one. So the order of the issue is valid by `isinstance`: each specific type comes before its parent.
- `FailureClass` has `provider`, `parser`, `plan_defect`, `ci_infra` and `head_moved` already. No new class is needed.
- `git grep` for `failed_class`, `failed_step`, `StepName` and `CLASS_BY_EXCEPTION` finds nothing in `src/`, `tests/` or `docs/`. No open or merged pull request touches them.
- `_plan_each` catches `AIClientError`, `RoadmapStageError` and `ToolExecutionError`, and builds the failure with `_failure_of`. `write_each` catches `DevOpsCLIError` and builds it with `_write_failure`. So the table covers every exception that reaches `StageFailure`.
- `_record_failures` writes the failure with one `set_marks` call. The two new keys go in that call.
- The tests in `tests/roadmap/stage/test_roadmap_stage_failure_class.py` and `tests/roadmap/test_roadmap_failure.py` run on the unchanged code and fail, because the keys, the enum and the table do not exist (`devops ci fail-to-pass --base origin/main`).
- Open point: `roadmap/failure.py` imports only `devops_cli.lang` today. The implement step adds the imports of the exception types and checks for an import cycle. `stage.py` already imports both modules, so the cycle risk is in the three other modules that import `failure.py` (`server/counter_series.py`, `stop_clear.py`, `digest_clears.py`).

## Existing Tool Considered

`FailureClass` and the table `ACTION_BY_CLASS` in `src/devops_cli/roadmap/failure.py` (#3065) and plain `isinstance` cover the need. No library maps an exception type to a project class. The change adds one enum, one tuple, one function and two record keys. The written cost: about 40,000 tokens and 2 hours to build, about 2,000 tokens each quarter to keep, and about 8,000 tokens and 0.5 hour to fix. No internal code is deleted.
