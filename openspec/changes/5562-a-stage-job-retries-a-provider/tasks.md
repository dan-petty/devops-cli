# Tasks

## 1. Retry a stage attempt whose failure class a retry can help

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `src/devops_cli/roadmap/job_result.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`. Changes: `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`.

- [ ] 1.1 Write first the case `test_a_provider_timeout_exits_75_and_keeps_the_check_out` in `tests/roadmap/stage/test_roadmap_stage_job_entry.py`: it calls `run_stage_job` with a `ModelFake` that answers `AIClientError` with status 504 and asserts `StageJobExit.EVICTED`, no `stage.job_result`, `stage.job` still naming the Job, the claim `owner/service`, and one result line with `class=provider infra=true`. Write `test_a_retried_attempt_after_a_provider_timeout_plans_and_stages_the_item`: a second `run_stage_job` after the 504 plans and stages the item without being blocked by failure wait. Write also `test_a_plan_defect_keeps_exit_1`, `test_a_refused_key_keeps_exit_1` and `test_a_clone_failure_exits_75`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stage/stage.py`, update `_failed_lately` so it does not skip an item whose check-out names the current Job (`item.job_record.get(StageRecordKey.JOB) == self._job`), allowing the retried pod to plan the item. In `src/devops_cli/roadmap/stage/stage_job.py`, add `_retries(failure)`: true when the failure is not None and `ACTION_BY_CLASS[failure]` is `FailureAction.RETRY`. Add `_attempt_failure(plan, applied, number)`: the class of the entry of `plan.failed` and `applied.failed` whose number is `number`, else None. In `run_stage_job`, after the result of the item, return `StageJobRun(StageJobExit.EVICTED, result.value, budget, plan=plan, applied=applied)` when `_retries` holds for that class, after `log_stage_attempts` when `known` is false or the check-out still names the Job, and write no check-in. Add `except AICredentialsError: raise` and `except DevOpsCLIError as exc:` after the handler of the time budget: the second writes `log_job_result` with `failure_class_of(exc)` under the same rule of the check-out and returns `StageJobExit.EVICTED` when `_retries` holds, else re-raises. Update `src/devops_cli/roadmap/stage/stage_submit.py` so recovery after backoff limit writes no duplicate result line when the pod already logged one. Update docstrings in `stage_job.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` passes

## 2. Update gate checks and documentation for retry exit 75

Kind: other. Reads: `tests/gate/k8s_checks/stage_job.py`, `docs/CLUSTER.md`, `docs/roadmap/stage.md`, `src/devops_cli/lang/en/help.py`, `docs/commands/roadmap.md`, `k8s/devops/cronjob-stage.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`. Changes: `tests/gate/k8s_checks/stage_job.py`, `docs/CLUSTER.md`, `docs/roadmap/stage.md`, `src/devops_cli/lang/en/help.py`, `docs/commands/roadmap.md`, `k8s/devops/cronjob-stage.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`.

- [ ] 2.1 Update the docstring of `check_the_stage_job_runs_again_only_after_an_eviction_and_ends_by_its_deadline` in `tests/gate/k8s_checks/stage_job.py:80` to document that exit 75 is used for both evictions and retryable failures, matching the existing `backoffLimit: 2` and `FailJob NotIn [75]` policy
  - Verification: `$ uv run devops ci --check --only k8s` passes
- [ ] 2.2 Update `docs/CLUSTER.md`, `docs/roadmap/stage.md:175`, `src/devops_cli/lang/en/help.py:1805-1808`, `docs/commands/roadmap.md:133`, `k8s/devops/cronjob-stage.yaml:32-36`, and `k8s/devops/roadmap-service/admissionpolicy.yaml:13,180` so they describe exit 75 for retryable failures keeping check-out and claim, and exit 1 for non-retryable failures
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test with a stage attempt that ends with class `provider` gets the retry exit code and a result line with `infra=true` (`devops ci fail-to-pass`).
- Group 1: A retried stage attempt after a provider timeout plans and stages the item.
- Group 1: A test with class `plan_defect` keeps exit code 1.
- Group 2: The k8s gate check docstrings and manifests consistently state exit 75 semantics.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
