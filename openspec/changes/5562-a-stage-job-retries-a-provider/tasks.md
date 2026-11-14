# Tasks

## 1. Retry a stage attempt whose failure class a retry can help

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/job_result.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `docs/CLUSTER.md`, `k8s/devops/cronjob-stage.yaml`. Changes: `src/devops_cli/roadmap/stage/stage_job.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `docs/CLUSTER.md`.

- [ ] 1.1 Write first the case `test_a_provider_timeout_exits_75_and_keeps_the_check_out` in `tests/roadmap/stage/test_roadmap_stage_job_entry.py`: it calls `run_stage_job` with a `ModelFake` that answers `AIClientError` with status 504 and asserts `StageJobExit.EVICTED`, no `stage.job_result`, `stage.job` still naming the Job, the claim `owner/service`, and one result line with `class=provider infra=true`. Write also `test_a_plan_defect_keeps_exit_1`, `test_a_refused_key_keeps_exit_1` and `test_a_clone_failure_exits_75`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stage/stage_job.py`, add `_retries(failure)`: true when the failure is not None and `ACTION_BY_CLASS[failure]` is `FailureAction.RETRY`. Add `_attempt_failure(plan, applied, number)`: the class of the entry of `plan.failed` and `applied.failed` whose number is `number`, else None. In `run_stage_job`, after the result of the item, return `StageJobRun(StageJobExit.EVICTED, result.value, budget, plan=plan, applied=applied)` when `_retries` holds for that class, after `log_stage_attempts` when `known` is false or the check-out still names the Job, and write no check-in. Add `except AICredentialsError: raise` and `except DevOpsCLIError as exc:` after the handler of the time budget: the second writes `log_job_result` with `failure_class_of(exc)` under the same rule of the check-out and returns `StageJobExit.EVICTED` when `_retries` holds, else re-raises. Update the `Ends` list of the module docstring: 1 for a failure whose class a retry cannot help, 75 for a failure whose class it can, with the check-out kept
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` passes
- [ ] 1.3 Edit `docs/CLUSTER.md` so the retries paragraph says that a stage attempt whose failure class has the action `retry` exits 75 and keeps its check-out and claim, and that any other failure of the item exits 1
  - Verification: `$ uv run devops ci docs` passes

## 2. Pin the retry code of the stage Job in the gate check

Kind: other. Reads: `k8s/devops/cronjob-stage.yaml`, `tests/gate/k8s_checks/job_admission_policy.py`, `tests/gate/k8s.py`, `src/devops_cli/k8s/cluster_job.py`. Changes: `tests/gate/k8s_checks/job_admission_policy.py`.

- [ ] 2.1 Add `check_the_stage_job_retries_only_exit_75` to `tests/gate/k8s_checks/job_admission_policy.py`, beside the other stage cases of the `k8s` row: it builds the stage Job with `_stage_job()` from CronJob `roadmap-stage` and asserts that `backoffLimit` is 2, that the pod failure policy holds one `Ignore` rule on `DisruptionTarget` and one `FailJob` rule with `onExitCodes` `NotIn` `[75]` for the container `stage`, and that the admission policy returns no refusal for that Job
  - Verification: `$ uv run devops ci --check --only k8s` passes

## Criteria

- Group 1: A test with a stage attempt that ends with class `provider` gets the retry exit code and a result line with `infra=true` (`devops ci fail-to-pass`).
- Group 1: A test with class `plan_defect` keeps exit code 1.
- Group 2: The policy test (`tests/gate/k8s_checks/job_admission_policy.py`) admits the stage Job with the new failure policy rule.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
