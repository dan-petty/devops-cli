# Proposal

## Why

The issue #4060 reports that a failed stage item waits for one fixed time. The setting `roadmap.stage.retry_hours` (default 6) holds it, and `_Judge._failed_lately` in `src/devops_cli/roadmap/stage/stage.py` reads it. A provider 5xx and a refused plan wait the same 6 hours. An item that changed while the job worked (`RoadmapItemChangedError`) also waits 6 hours, and it needs no wait.

The issue #4056 put the failure class in the job record of the item (`stage.failed_class`). Nothing reads it. The wait must follow the class, so a transient error is tried again soon and a refused plan waits for a person or for a change of the item.

## What Changes

- Add `RETRY_AFTER` to `src/devops_cli/roadmap/failure.py`: a read-only mapping from `FailureClass` to `timedelta`, built as `ACTION_BY_CLASS` is. The values are `provider` 1 hour, `parser` 6 hours, `plan_defect` 6 hours, `ci_infra` 1 hour and `head_moved` 0. It has no `None` value. Its keys are the five classes that `CLASS_BY_EXCEPTION` gives, and a test holds that the keys are exactly those classes.
- Change `_Judge._failed_lately`: it reads `stage.failed_class` from the job record and waits until `failed_at + RETRY_AFTER[class]`. It does not store that time. A record with no class, and a record with a class that is no `FailureClass`, wait as `ci_infra`. A failure time that is no time still holds the item for no time. `--item` still overrules the wait.
- Remove the setting `roadmap.stage.retry_hours` (`RoadmapStageConfig.retry_hours` in `src/devops_cli/config/settings.py`) and the default `DEFAULT_ROADMAP_STAGE_RETRY_HOURS` in `src/devops_cli/config/defaults.py`. The `_Judge` constructor and `select_stageable` read no setting for the wait. Add no shim.
- Remove the entry for the default from the table of limit classes in `tests/roadmap/test_roadmap_limit_classes.py`, and change `tests/roadmap/stage/test_roadmap_stage_retry.py` to the new wait.
- Fix each place that names the setting: the comments in `src/devops_cli/roadmap/stage/stage.py` and `src/devops_cli/roadmap/run.py`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `k8s/README.md` (item 15 of the list of the Roadmap service), and `docs/CONFIGURATION.md` (generated with `devops docs generate`).
- Change the requirement "A failed item waits for the retry delay" in `roadmap-stage` and the requirement "The command reports an item that the stage job holds for a retry" in `roadmap-explain`, and add the requirement "A failure class has a wait" to `roadmap-failure-taxonomy`. The wait is behavior that a person observes in `explain` and in the stage selection, so the change carries a spec delta.
- Rollout: the live ConfigMap needs no change (see Feasibility). `RoadmapStageConfig` ignores an unknown key, so a stale `retry_hours` in a config file does not fail the settings load. A test holds this.
- Not in this change: a comment on the issue for a class whose action is `wait` (no stage failure maps to such a class), and the output of `inbox` (#3648).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A failed item waits for the retry delay
- `roadmap-explain`: The command reports an item that the stage job holds for a retry
- `roadmap-failure-taxonomy`: A failure class has a wait

## Impact

- Code: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_retry_after.py`, `tests/roadmap/stage/test_roadmap_stage_retry.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_limit_classes.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/CONFIGURATION.md`, `k8s/README.md`

## Feasibility

- I read `src/devops_cli/roadmap/failure.py` at origin/main `23357542`. `CLASS_BY_EXCEPTION` (line 130) maps to exactly five classes: `head_moved`, `parser`, `provider`, `plan_defect` and `ci_infra`. So `RETRY_AFTER` has five keys, as the issue lists.
- `StageRecordKey.FAILED_CLASS` exists (`src/devops_cli/roadmap/stores/store.py:242`). `stage.py` writes it as `failure.failure_class.value` and clears it where it clears `stage.failed_at`. Nothing reads it, so the class is there for this change to read.
- `_Judge._failed_lately` in `src/devops_cli/roadmap/stage/stage.py` computes `failed_at + self._retry`. `self._retry` is one `timedelta` that `select_stageable` builds from `load_settings().roadmap.stage.retry_hours`. This is the only reader of the setting, so the setting can go with it.
- Grep of `retry_hours` outside `openspec/changes/archive`, run in the worktree, found: `src/devops_cli/roadmap/stage/stage.py` (6 lines), `src/devops_cli/roadmap/run.py` (1), `src/devops_cli/config/settings.py` (import and field), `src/devops_cli/config/defaults.py` (1), `docs/CONFIGURATION.md` (generated), `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `k8s/README.md`, the two specs, and the two test files. `docs/ENV_VARS.md` has no entry, because the setting is not a `Variable()`. `k8s/devops/configmap.example.yaml` has no `retry_hours`.
- Rollout rule, checked read-only: `kubectl -n devops get cm devops-cli-config -o jsonpath='{.data}'` holds `roadmap.stage` with `filter`, `limit`, `planned_limit`, `step_tokens` and `toolset`, and no `retry_hours`. A search of the output for `retry_hours` finds 0 matches. So the live ConfigMap needs no change before the image rolls.
- The issue says that an unknown key can fail the settings load. That is wrong for this model. `RoadmapStageConfig.model_config` is `{'extra': 'ignore', ...}`; a run of `RoadmapStageConfig(retry_hours=2, bogus_key=1)` gives an object with no `bogus_key`. A stale key is ignored, and a test (`test_a_config_file_that_still_names_retry_hours_loads_and_the_setting_is_gone`) holds this. The key-walk test of the example ConfigMap (`tests/config/test_k8s_devops_runtime.py`, #4093) already proves that the example ConfigMap loads into `Settings`.
- The tests fail on `origin/main` for the right reason, run with `uv run devops ci test`: a provider and an `ci_infra` failure of 1 hour are still held (the wait is 6 hours), an item that changed is still held, `RETRY_AFTER` is missing, and the setting `retry_hours` is still a field. A parser failure and a refused plan pass on the base, because their wait is 6 hours today as well.
- No upstream document or library is involved: the change reads project code only.

## Existing Tool Considered

No library covers a table of project failure classes and waits. A `Mapping` as in `ACTION_BY_CLASS` (`types.MappingProxyType`) is enough, and `datetime.timedelta` holds the wait. The change builds one table of five entries and one lookup. Cost, as the issue states it: about 45,000 tokens and 2.5 hours to build, about 2,000 tokens a quarter to keep, and about 10,000 tokens and 1 hour to fix. The change deletes the setting `roadmap.stage.retry_hours`, its default, the `_retry` argument of `_Judge`, and the table entry and tests that name them.

## Dependencies

The issue #4056 (the class in the record) is merged. The issues #4061 and #4065 follow this change.
