# Proposal

## Why

The recovery paths of the stage and implement jobs are trusted only after a fault hits a live item: an OOM, a 25-minute generation, an XML parser error, a wrong plan path, a scratch file in the root. #3075 asks for an offline fault-injection suite that makes each fault happen and proves that the job recovers, names the class and the action, posts the right comment, and keeps the finished work.

## What Changes

- Add `tests/roadmap/test_roadmap_faults.py`, a parametrized table of one stage or implement fault case for every class of `FailureClass`, with the coverage gate and the count gate.
- Add `tests/roadmap/test_roadmap_run_state_faults.py` for the Service state files: a halt record that cannot be written, and an unreadable `schedule.json`, failure ledger and intake record.
- Add `tests/roadmap/test_roadmap_run_row_faults.py` for the Service rows: a `RoadmapItemChangedError` during intake apply, a Service stop between two stage items, and a failed marks write after the draft pull request exists.
- State the measured duration of the three fault modules in the docstring of `tests/roadmap/test_roadmap_faults.py` and hold it under the 60-second bound of the Tests & Coverage check.
- The change adds tests only, so it has no spec delta: every path of the change is under `tests/`, and no command, option, manifest or service behavior changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/roadmap/test_roadmap_faults.py`, `tests/roadmap/test_roadmap_run_state_faults.py`, `tests/roadmap/test_roadmap_run_row_faults.py`

## Feasibility

- The probe `The path `src/devops_cli/roadmap/failure.py` is a file of the staging commit.` confirms the taxonomy that every case keys on.
- The probe `The path `tests/support/fakes/model.py` is a file of the staging commit.` and the probe `The path `tests/support/fakes/process.py` is a file of the staging commit.` confirm the model and process fakes, and the probe lines for `tests/support/fakes/git.py`, `tests/support/fakes/kubernetes.py`, `tests/support/fakes/roadmap_store.py` and `tests/support/fakes/clock.py` confirm the git, cluster, store and clock fakes.
- The probe `The path `docs/TESTING.md` is a file of the staging commit.` confirms the testing document, whose line `docs/TESTING.md:141` holds `No test bounds elapsed wall-clock time from above.`
- `search_code` with `test_roadmap_faults` returned no match, and `list_files` of `tests/roadmap` holds no fault file, so the suite is new.
- `search_code` with `def test_each_class_has_exactly_one_default_action_in_one_table` shows `tests/roadmap/test_roadmap_failure.py:494` holds `def test_each_class_has_exactly_one_default_action_in_one_table() -> None:`, the test that compares `ACTION_BY_CLASS` with `FailureClass`, which the coverage gate copies.
- `search_code` with `ACTION_BY_CLASS: Final` shows `src/devops_cli/roadmap/failure.py:84` holds `ACTION_BY_CLASS: Final[Mapping[FailureClass, FailureAction]] = MappingProxyType(`, so the expected action of a case comes from the one table.
- `read_file` of `src/devops_cli/roadmap/implement/implement_run.py` shows the stop path: `src/devops_cli/roadmap/implement/implement_run.py:1544` holds `self.store.comment(` and `src/devops_cli/roadmap/implement/implement_run.py:1582` holds `derive_status(StatusFacts(stopped=True)),`, so a case asserts the posted comment and the final label.
- `read_file` of `src/devops_cli/roadmap/run.py` shows `src/devops_cli/roadmap/run.py:233` holds `def _read_schedule(schedule_path: Path) -> dict[str, datetime]:`, `src/devops_cli/roadmap/run.py:272` holds `def read_intake_record(path: Path) -> IntakeRecord:` and `src/devops_cli/roadmap/run.py:1044` holds `class FailureLedger:`.
- `read_file` of `src/devops_cli/roadmap/run.py` shows `src/devops_cli/roadmap/run.py:250` holds `except OSError, json.JSONDecodeError:`, so a `schedule.json` that is not JSON reads as no time and the row runs.
- `read_file` of `src/devops_cli/server/service.py` shows `src/devops_cli/server/service.py:158` holds `def keep_state_record(record: Path, payload: object) -> None:` and `src/devops_cli/server/service.py:165` holds `except OSError as exc:`, so a halt record that cannot be written is one error log line and the halt stays in memory.
- The defect of the earlier plan is real: `src/devops_cli/server/service.py:343` holds `self._halted = halt_record is not None and halt_record.exists()`, so a directory at the halt record's path starts the Service halted and `_halt` never writes. The plan now puts a regular file where the halt record's parent directory would be: `Path.exists` on the record is then False, and `keep_state_record` reaches `write_json_file`, whose `mkdir` of the parent raises `NotADirectoryError`, an `OSError`, so the error line is written and no record file is made.
- `read_file` of `src/devops_cli/output/file_writer.py` shows `src/devops_cli/output/file_writer.py:37` holds `target_path.parent.mkdir(parents=True, exist_ok=True)`, the line that raises on a parent that is a regular file.
- `read_file` of `src/devops_cli/roadmap/intake/intake.py` shows `src/devops_cli/roadmap/intake/intake.py:1315` holds `def apply_intake(` and `src/devops_cli/roadmap/intake/intake.py:1330` holds `except GitHubOperationError as exc:`, so a `RoadmapItemChangedError` is caught as a failed candidate and named by `raise_for_failed_placements`, which posts no comment.
- `search_code` with `RoadmapItemChangedError` shows `src/devops_cli/roadmap/stores/store.py:759` raises it, so the intake-apply fault is reachable through the in-memory store's `fail_write`.
- `search_code` with `store.set_marks(` shows `src/devops_cli/roadmap/stage/stage.py:1883` holds `store.set_marks(`, and `src/devops_cli/roadmap/stage/stage.py:1946` holds `def _write_failure(item: Item, exc: DevOpsCLIError) -> StageFailure:`, so a failed marks write after the pull request is opened is recorded as the error class and its masked text, and no staged comment is posted.
- `search_code` with `ServiceStoppingError` shows `src/devops_cli/exceptions/roadmap.py:40` holds `class ServiceStoppingError(RoadmapRunError):` and `src/devops_cli/roadmap/run.py:561` holds `except ServiceStoppingError:`, so the stop between two stage items ends the round as a stop and not as a failed round.
- `read_file` of `tests/support/roadmap_implement.py` shows `tests/support/roadmap_implement.py:480` holds `class JobWorld:` and `tests/support/roadmap_implement.py:505` holds `def run(`, so a case drives the real implement job on the fakes.
- `read_file` of `tests/support/roadmap_run.py` shows `tests/support/roadmap_run.py:392` holds `def poll_round(` and `tests/support/roadmap_run.py:542` holds `def lane_table(`, so a row case runs one lane round on the in-memory store.
- `apply_implement` needs a checkout of the repository at `JobWorld.repo.clone`, a client of the store, which `InMemoryRoadmapStore` gives, and a model client, which `ModelScript` gives with no network.
- `plan_implement` needs a checkout of the repository and a client of the store, both from the `job_world` fixture.
- `run_due_jobs` and `STAGE_ROW.runner` need a checkout of the repository at the lane's clone path and a client of the store, which `lane_table` and `InMemoryRoadmapStore` give.
- `read_intake_record`, `FailureLedger` and `keep_state_record` need a path under `tmp_path` and no network.
- `RoundPause.after` needs a clock, which the `clock` fixture gives, and no network.
- The `FailureClass` enum in `src/devops_cli/roadmap/failure.py` holds 19 members, counted from the source in the inputs: provider, parser, test, lint, types, plan_defect, premise_false, oom, timeout, refused_tool, conflict, ci_infra, no_change_in_fix, tests_lost, head_moved, output_cap, read_only_path, limit_reached and outside_plan. Each member stays and is restricted to the one case that group 1 gives it: provider to a provider HTTP 500, parser to a malformed tool call, test to a failing pytest log, lint to a failing ruff log, types to a failing mypy log, plan_defect to an unticked task group, premise_false to a false premise, oom to exit status 137, timeout to exit status 143, refused_tool to a refused command, conflict to a non-fast-forward push, ci_infra to a check whose log shows nothing, no_change_in_fix to a fix step that changes no file, tests_lost to a lost test, head_moved to a moved head, output_cap to an output cap, read_only_path to a read-only path, limit_reached to a reached limit and outside_plan to a change outside the plan. No member is removed and none is allowlisted, so the coverage gate of group 1 names a class that has no case.
- The earlier plan's second defect is real: group 3 added row cases and measured no time, so the 60-second criterion now belongs to group 4, whose `process` measures the three fault modules and holds the total under 60 seconds.
- The first checks against the real system are `uv run devops ci test tests/roadmap/test_roadmap_faults.py`, then `uv run devops ci test tests/roadmap/test_roadmap_run_state_faults.py`, then `uv run devops ci test tests/roadmap/test_roadmap_run_row_faults.py`, then the whole check `uv run devops ci`.

## Existing Tool Considered

pytest, already the project's runner (`pyproject.toml` sets `[tool.pytest.ini_options]`), with pytest-timeout for the hang bound and pytest-xdist for the workers. The repository's edge fakes cover every edge: `model_fake` in `tests/support/fakes/model.py`, `process_fake` in `tests/support/fakes/process.py`, `git_fake` in `tests/support/fakes/git.py`, `cluster` in `tests/support/fakes/kubernetes.py`, the in-memory roadmap store in `tests/support/fakes/roadmap_store.py` and the clock fixture in `tests/support/fakes/clock.py`. The change adds cases to that runner and no tool.

## Dependencies

- #4097: docs/TESTING.md — the open pull request changes the testing document that this plan reads for the rule that no test bounds elapsed time; that rule stays the same.
