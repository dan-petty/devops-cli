# Design

## Decisions

- **Reuse exit 75 for a failure whose class a retry can help.**: `k8s/devops/cronjob-stage.yaml:37:backoffLimit: 2` and `:47:values: [75]` already retry only exit 75, so the Job controller runs the pod again with no manifest change.
- **Take the class from the action of `ACTION_BY_CLASS`, not from a second list.**: `src/devops_cli/roadmap/failure.py:118:ACTION_BY_CLASS` is the one table of the action of each class, and `src/devops_cli/roadmap/stop_clear.py:199` already reads it for the same question.
- **Write no check-in for an attempt that exits 75.**: `src/devops_cli/roadmap/stage/stage_job.py:270:StageRecordKey.FAILED_AT` and the failed class are written by a check-in, and the next pod's selection leaves an item in its failure wait out, so the retry would plan nothing.
- **Write the result line of the attempt from the pod, under the rule of the check-out.**: `src/devops_cli/roadmap/stage/stage_job.py:388:known = _known(store, item, settings.job)` gives the rule that keeps one line for each attempt: the pod writes it when the check-out names its Job or when none named it at its start.
- **Keep the pod failure policy and the admission policy unchanged, and pin the retry code in the gate check.**: `k8s/devops/cronjob-stage.yaml:43` already holds `action: FailJob` on each code but 75, and `tests/gate/k8s_checks/job_admission_policy.py` already judges the stage Job, so the change adds a case there instead of a manifest rule.
- **Verify the gate case with the `k8s` row of `devops ci`, not with pytest.**: `tests/gate/k8s.py:17` runs the module's `check_*` functions through `tests/gate/runner.py`, and pytest collects no `check_*` function, so `devops ci test` on the module proves nothing about the case.
- **Re-raise `AICredentialsError` so it keeps exit 1.**: `src/devops_cli/ai/client/models.py:144:class AICredentialsError(AIClientError)` and `src/devops_cli/roadmap/failure.py:151:(AIClientError, FailureClass.PROVIDER)` would read a refused key as `provider` and spend the two retries on it.
- **Leave the gateway unchanged and name the fallback in the pull request.**: The issue defers the gateway to a separate item, and this change reads and edits no gateway file.
- **Keep each changed requirement text under the 500-character limit and state the detailed outcomes in its scenarios.**: The stage check refuses a requirement text over 500 characters, and the scenarios of the two requirements already name the record keys, the claim and the result line that a test asserts.

## Rejected alternatives

- **Add a new exit code for a retryable failure.**: It needs a change to `k8s/devops/cronjob-stage.yaml:47:values: [75]` and to the admission policy that pins the rule, and it buys no retry that exit 75 does not already have.
- **Retry every class with `infra=true`.**: `src/devops_cli/roadmap/job_result.py:125:INFRA_CLASSES` also holds `oom` and `limit_reached`, whose action is `raise_limit` at `src/devops_cli/roadmap/failure.py:127:FailureClass.OOM: FailureAction.RAISE_LIMIT,`, and a new pod cannot raise a limit.
- **Check in with the failure and exit 75.**: `src/devops_cli/roadmap/stage/stage_job.py:270:StageRecordKey.FAILED_AT` records the failure time, and the next pod's selection leaves the item in its wait out, so the retry plans nothing.
- **Leave the retry to the next round of the Service.**: `src/devops_cli/roadmap/failure.py:169:FailureClass.PROVIDER: timedelta(hours=1),` makes the item wait an hour for a timeout that is often over in seconds, and the round also creates a new Job.
- **Catch the model error and exit 75 only when it is raised.**: `src/devops_cli/roadmap/stage/stage.py:2463:except (AIClientError, RoadmapStageError, ToolExecutionError) as exc:` turns the model error of an item into a failed result, so a handler on the raised error alone would never see a provider timeout.
- **Verify the gate case with `devops ci test` on the gate module.**: `tests/gate/runner.py:45:if name.startswith("check_") and function.__module__ == module.__name__` selects the `check_*` functions and pytest collects none of them, so that command runs no case and passes whatever the module holds.
- **Split the exit-code rule into a new requirement of the capability.**: The capability already holds `The stage Job ends with the exit code of its end and checks in`, which `read_spec` shows with the same exit codes, so a second requirement would repeat it and a `modified` entry replaces it.

## Security

The stage Job's manifest and the keys of its pod stay as they are: this change reads `k8s/devops/cronjob-stage.yaml` and edits no file under `k8s/`, so the pod still takes two keys of Secret `devops-cli`, mounts no service account token and keeps its policy. A person must confirm that a pod that exits 75 keeps the check-out `stage.job` and the claim `owner/service`, because the retry depends on it and no second pod may plan the same item. `tests/roadmap/stage/test_roadmap_stage_job_entry.py` fails if such an attempt writes `stage.job_result` or releases the claim, and `tests/gate/k8s_checks/job_admission_policy.py` fails if the retry rule of the Job changes.
