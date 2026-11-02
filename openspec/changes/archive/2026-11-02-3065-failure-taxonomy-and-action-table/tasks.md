# Tasks

## 1. Classify a failure and give each class one action

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/failure.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_failure.py` (new).

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_failure.py` for the scenarios of "The failure classes", "A pure classifier", "Real excerpts map to their class", "One default action for each class" and "The action left": a table over the stop texts of #2175, #2735 and #2747, the failed-test text of #2924 and the messages of the job, which covers all 12 classes; the table of actions; the lines of the comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py` fails on the base
- [x] 1.2 Add `failure.py` with the classes, the actions, `ACTION_BY_CLASS`, `classify_failure`, `left_action` and `failure_lines`, and the messages of the lines
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py`

## 2. Name the class in the stop comment, the record and the trace

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/stop_clear.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_job_scoped.py`, `tests/roadmap/test_roadmap_stop_clear.py`.

- [x] 2.1 Write failing tests for the scenarios of "The stop comment names the failure class": the comment of a step that changed no file, the log line, the comment after fix rounds that did not pass a check, the removal of the record by a retry and by a clear rule
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_job_scoped.py tests/roadmap/test_roadmap_stop_clear.py` fails on the base
- [x] 2.2 Add the key `implement.failure`, the evidence on the stop of the job (`status`, `check` and the fix rounds), the class in the comment, the record and the log line, and the removal of the key with the stop
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_job_scoped.py tests/roadmap/test_roadmap_stop_clear.py`

## 3. Count the failures by class in the Service

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/telemetry/metrics.py`. Changes: `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_submit.py`.

- [x] 3.1 Write failing tests for the scenarios of "The Service counts the failures by class": a stop of the runner counted once under its class, a Job with no result that gets the class of its log, and a Job with a result that adds nothing
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py` fails on the base
- [x] 3.2 Add the counter `devops_cli_service_implement_failures_total`, the class of a Job with no result, and the lines in its report
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py`

## 4. Document the classes, the record key and the metric

Kind: documents. Reads: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`.

- [x] 4.1 Add `implement.failure` and the table of classes and default actions to `docs/ROADMAP_WORKFLOW.md`, and the counter to the `/metrics` list of `k8s/README.md`
  - Verification: `uv run devops ci --check --only docs`

## 5. Archive the change

Kind: other. Changes: `openspec/changes/3065-failure-taxonomy-and-action-table`, `openspec/specs/roadmap-failure-taxonomy/spec.md`, `openspec/specs/roadmap-implement-job/spec.md`.

- [x] 5.1 Archive the change after every task is ticked
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- The dispatch of `change_tier` belongs to #3060, the model ladder.
- The dispatch of `raise_limit`, and the termination reason of a pod for the class `oom`, belong to #3062, the durable runs.
- The dispatch of `retry`, `amend` and `return` from the class of a partial implementation belongs to #3098.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
