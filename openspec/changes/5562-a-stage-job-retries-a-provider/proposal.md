# Proposal

## Why

The stage Job of #5562 exits 1 for an attempt that a provider timeout ends, and the pod failure policy of CronJob roadmap-stage fails the Job on exit 1, so Kubernetes runs no new pod and the item waits for the next round of the Service. The change gives that end the one retry code of the Job, so the Job controller runs the pod again at once and the next pod plans the same item.

## What Changes

- Map the class of a stage attempt through `ACTION_BY_CLASS` in `src/devops_cli/roadmap/stage/stage_job.py`, and exit 75 for a class whose action is `retry`.
- Write the result line of that attempt with its class and `infra=true`, and write no check-in, so `stage.job` and the claim `owner/service` stay for the next pod.
- Keep exit 1 for a class that a retry cannot help, such as `plan_defect`, for a plan that its own checks refused, and for a refused key of the provider, and keep exit 143 for the deadline end.
- Pin the retry code of the stage Job in `tests/gate/k8s_checks/job_admission_policy.py`, which the `k8s` row of `devops ci` runs: exit 75 is the only code that the pod failure policy and `backoffLimit: 2` retry.
- State the new end in `docs/CLUSTER.md`, and keep the gateway fallback for `deepseek-v4.1-flash-1017` out of this change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/job`: The stage Job ends with the exit code of its end and checks in, The stage Job writes one result line for its attempt after its check-in

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_job.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `tests/gate/k8s_checks/job_admission_policy.py`

## Feasibility

- The premise holds. The probe says "`StageJobExit` defines the field `FAILURE` at src/devops_cli/roadmap/stage/stage_job.py:141", and `read_file` shows src/devops_cli/roadmap/stage/stage_job.py:429:`exit_code = StageJobExit.FAILURE if result in _FAILED else StageJobExit.RESULT`, so a failed plan exits 1.
- The probe says "The path `roadmap/stage/stage_job.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_job.py`, `tests/gate/k8s_checks/stage_job.py`. No commit in the history deleted or renamed it." The change uses `src/devops_cli/roadmap/stage/stage_job.py`.
- The probe says "The path `roadmap/failure.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/failure.py`. No commit in the history deleted or renamed it." The change reads `src/devops_cli/roadmap/failure.py` and changes it not.
- `read_file` of src/devops_cli/roadmap/stage/stage_job.py:142 shows `EVICTED = 75`, the one code that the pod failure policy retries, and :416:`return StageJobRun(StageJobExit.EVICTED, kill.value, budget, kill=kill)` gives it today only to a SIGTERM before the time budget ends.
- `read_file` of k8s/devops/cronjob-stage.yaml shows :37:`backoffLimit: 2`, :43 `action: FailJob` and :47:`values: [75]`, so exit 75 is the only retried code and the manifest needs no change.
- `read_file` of src/devops_cli/roadmap/failure.py:118 shows `ACTION_BY_CLASS: Final[Mapping[FailureClass, FailureAction]] = MappingProxyType(`. Its 20 entries at lines 120 to 139 give the action of each of the 20 classes of the taxonomy: 4 hold `RETRY` at :120, :128, :131 and :134, and the 16 others hold another action. The new guard over the 20 classes retries those 4 and keeps exit 1 for the 16, each decided by the table and none allowlisted by name.
- The same derivation already exists: tests/roadmap/test_roadmap_stop_clear.py:39:`RETRY_CLASSES = [c for c, action in ACTION_BY_CLASS.items() if action is FailureAction.RETRY]`, and src/devops_cli/roadmap/stop_clear.py:199:`return klass if ACTION_BY_CLASS.get(klass) is FailureAction.RETRY else None` asks the table the same question.
- A provider timeout reaches the Job as a failed item, not as a raised error: src/devops_cli/roadmap/stage/stage.py:2463:`except (AIClientError, RoadmapStageError, ToolExecutionError) as exc:` records a `StageFailure` with :2419:`failure_class=failure_class_of(exc),`. The change therefore reads the class of the failed item and the class of a raised error.
- `read_file` of src/devops_cli/roadmap/stage/stage_job.py:426 to 428 shows the check-in and :428:`log_stage_attempts(plan, applied, repo=repo)`, so the result line of a failed plan already holds the class at this commit. The change keeps that one writer of the line and changes the exit code and the check-in.
- `read_file` of src/devops_cli/roadmap/stage/stage_job.py:253:`if item is None or item.job_record.get(StageRecordKey.JOB) != job:` and :270:`StageRecordKey.FAILED_AT: now.isoformat(),` show that a check-in clears the check-out and records the failure time, which is why the retry end writes no check-in: the next pod's selection would leave the item in its failure wait.
- `read_file` of src/devops_cli/roadmap/stage/stage_submit.py:380:`if old is not None and old.state is not JobState.RUNNING and name not in deleted:` shows the Service deletes a finished Job of the same name before a new create, so a retried pod and a later round do not collide.
- `read_file` of src/devops_cli/roadmap/stage/stage_job.py:388:`known = _known(store, item, settings.job)` gives the rule of the line: the pod writes it when the check-out names its Job or when no check-out named it at its start.
- `read_file` of src/devops_cli/ai/client/models.py:144:`class AICredentialsError(AIClientError):` and src/devops_cli/roadmap/failure.py:151:`(AIClientError, FailureClass.PROVIDER),` show that a refused key would read as `provider` and exit 75, so the handler re-raises it and it keeps exit 1.
- `read_file` of src/devops_cli/roadmap/stage/stage.py:2461 to 2462 shows `except AICredentialsError:` then `raise`, so a refused key leaves the plan as a raised error and reaches the Job.
- `read_file` of docs/CLUSTER.md:78:`A result exits 0, and a failure of the item exits 1.` states the old rule, so the plan edits that sentence.
- The review finding is corrected. The `check_*` functions of a gate module are not pytest tests: `tests/gate/k8s.py:17:`return run_checks("k8s", k8s_checks)`` calls them, and `tests/gate/runner.py:45:`if name.startswith("check_") and function.__module__ == module.__name__`` selects them by name, so group 2 no longer runs `devops ci test` on the module. It runs `uv run devops ci --check --only k8s`, the row that `src/devops_cli/commands/ci.py:983:`cmd=_python_check_cmd("k8s"),` defines, and the row fails when `check_the_stage_job_retries_only_exit_75` fails.
- No command or verify program is new. Group 1 verifies with `uv run devops ci test`, and `uv`, `python`, `pytest` and `devops` are in the runner image. Group 2 verifies with the `k8s` row, whose render starts `kubectl kustomize` (`tests/gate/k8s_render.py:38:`["kubectl", "kustomize", str(directory)],`), and `kubectl` is `NOT_IN_RUNNER`: a runner pod cannot render the manifests, so the pull request's Static Analysis job runs that row and the fail-to-pass check replays the changed module on the base and the head.
- The pod settings that apply are those of the stage pod, unchanged: `allowPrivilegeEscalation: false`, `capabilities.drop: ALL`, `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `seccompProfile: RuntimeDefault` in `k8s/devops/cronjob-stage.yaml`.
- Precondition of `run_stage_job` with no `source`: `_clone` at src/devops_cli/roadmap/stage/stage_job.py:363 needs a checkout of the repository and a network, because `status_clone` clones it blobless.
- Precondition of `plan_stage`: it needs a checkout of the repository in `source` and a client of the gateway over the network for each model call.
- Precondition of `check_in` and `_known`: each needs a client of the roadmap store, which reads and writes GitHub. The tests of the plan use the in-memory store and reach no network.
- Precondition of `log_job_result` and `log_stage_attempts`: none, because each writes a log line and reads no checkout, client or network.
- The gateway fallback for `deepseek-v4.1-flash-1017` is not checked: no tool call read k8s/llm/gateway/config.yaml, and the issue defers the gateway to a separate item, so this change touches no gateway file.
- The open items that name the stage Job are not checked: the run reached its tool budget before a search of open items. The context lists one overlap, #5577, and the plan records it as a dependency entry.

## Existing Tool Considered

Kubernetes' Job controller covers the need: `backoffLimit: 2` and the `podFailurePolicy` of CronJob `roadmap-stage` already run the pod again after exit 75 and fail the Job on every other code, so the change maps the failure class to that code and adopts no library.

## Dependencies

- #5577 shares `k8s/llm/gateway/config.yaml` with the gateway fallback that #5562 names; this change edits no gateway file, so it neither waits on #5577 nor conflicts with it.
