# Tasks

## 1. Add the server start seam and its contract test

Kind: behavior. Reads: `src/devops_cli/commands/serve.py`, `src/devops_cli/telemetry/tracer.py`, `tests/conftest.py`, `tests/support/fakes/otlp.py`, `docs/TESTING.md`, `tests/server/test_server.py`. Changes: `src/devops_cli/server/start.py` (new), `tests/support/fakes/server.py` (new), `tests/server/test_server_start_seam.py` (new), `tests/conftest.py`.
Adds: `ServerStarter`, `StartCall`, `UvicornStarter`, `FakeServerStarter`, `get_server_starter`, `install_server_starter`, `remove_server_starter`

- [ ] 1.1 `test_the_real_starter_serves_a_request_on_a_loopback_port_and_stops` in `tests/server/test_server_start_seam.py`: a `FakeServerStarter` installed with `install_server_starter` records one start call and builds one app from the factory, `UvicornStarter` serves one request on a loopback port that the test process binds and stops, the fake records the same host, port, factory flag and log config for that call, and `remove_server_starter` gives `get_server_starter` the real starter again
  - Verification: `$ uv run devops ci test tests/server/test_server_start_seam.py` fails on the base
- [ ] 1.2 Write the contract case first. Add `ServerStarter`, `StartCall`, `UvicornStarter`, `get_server_starter`, `install_server_starter` and `remove_server_starter` in `src/devops_cli/server/start.py`, in the shape of `install_exporter` in `src/devops_cli/telemetry/tracer.py`. `StartCall` holds the target and the options of one start; `UvicornStarter.start` calls `uvicorn.run`; `UvicornStarter.config` gives the `uvicorn.Config` of the same call, so the contract test runs `uvicorn.Server` on it, serves one request on a loopback port that the test process binds, and stops it. Add `FakeServerStarter` in `tests/support/fakes/server.py`: it records a `StartCall` and, when the call sets `factory`, builds the app by calling the target and keeps it in `apps`, as uvicorn does, so no case builds the app outside the start. Add `devops_cli.server.start` with `remove_server_starter` to `_PROCESS_STATE_RESETS` in `tests/conftest.py`
  - Verification: `$ uv run devops ci test tests/server/test_server_start_seam.py` passes

## 2. Start the server of serve through the installed starter

Kind: behavior. Reads: `src/devops_cli/commands/serve.py`, `tests/server/test_server.py`, `tests/roadmap/test_roadmap_run_service.py`, `tests/support/fakes/server.py`. Changes: `src/devops_cli/commands/serve.py`, `tests/server/test_server.py`, `tests/roadmap/test_roadmap_run_service.py`.

- [ ] 2.1 `test_serve_service_mode_success` in `tests/server/test_server.py`: with `FakeServerStarter` installed, `devops serve --service --host ::1 --port 8787` exits 0 and records one start call with host `::1`, port `8787`, the factory flag and the service log config. `test_serve_service_mode_hands_the_starter_an_app_factory_and_the_json_log_config` in the same module: the recorded call sets `factory` and `log_config`, the fake builds exactly one app, and the missing-secret warning of `example-org/repo2` is in `caplog`. `test_the_service_that_serve_starts_reads_its_halt_and_budget_from_the_volume` in `tests/roadmap/test_roadmap_run_service.py` reads `state.service_manager` of the app that the fake built, with no patch of `uvicorn.run`
  - Verification: `$ uv run devops ci test tests/server/test_server.py tests/roadmap/test_roadmap_run_service.py` fails on the base
- [ ] 2.2 In `src/devops_cli/commands/serve.py`, drop the `import uvicorn` and replace the three `uvicorn.run` calls with `get_server_starter().start(...)`: the service branch passes `partial(create_service_app, ...)` with `factory=True` and `log_config=service_log_config(log_level)`, and the REST branch passes the app, or the import string with `factory=True` under `--reload`. In `tests/server/test_server.py`, install `FakeServerStarter` in the seven cases that patch `uvicorn.run` and read the recorded start call in place of the mock; the two dry-run cases install a fake whose `start` fails the case. Rename `test_serve_service_mode_builds_the_app_after_the_server_applies_its_logging` to `test_serve_service_mode_hands_the_starter_an_app_factory_and_the_json_log_config`, and assert the `factory` flag, the log config, the one app that the fake built and the missing-secret warning in `caplog`, so the case checks the start call and never calls the factory itself. In `tests/roadmap/test_roadmap_run_service.py`, install `FakeServerStarter` in `test_service_wiring` and in the halt and budget case, and read each app from `fake.apps`; the `run_due_jobs` patch of `test_service_wiring` stays until the lane group removes it
  - Verification: `$ uv run devops ci test tests/server/test_server.py tests/roadmap/test_roadmap_run_service.py` passes

## 3. Put each lane's table and clone directory on the app state

Kind: behavior. Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/commands/serve.py`, `tests/roadmap/test_roadmap_run_lane_table.py`, `tests/roadmap/test_roadmap_run_service.py`, `tests/support/fakes/server.py`, `tests/server/test_server.py`. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/commands/serve.py`, `tests/roadmap/test_roadmap_run_lane_table.py`, `tests/roadmap/test_roadmap_run_service.py`.
Adds: `LaneSpec`, `lane_specs`

- [ ] 3.1 `test_each_lane_spec_holds_its_table_and_clone_directory` in `tests/roadmap/test_roadmap_run_lane_table.py`: `lane_specs` gives one `LaneSpec` for each lane of `service_lanes`, in the order of the due table, with the rows of its lane and the clone directory `lanes/<lane>`, and `service_jobs` builds one job for each spec. `test_service_wiring` in `tests/roadmap/test_roadmap_run_service.py` installs `FakeServerStarter`, reads the app that the fake built, and finds one `LaneSpec` in `app.state.lanes` for each key of `app.state.jobs`, with no `run_due_jobs` patch
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lane_table.py tests/roadmap/test_roadmap_run_service.py` fails on the base
- [ ] 3.2 Add `LaneSpec` and `lane_specs` in `src/devops_cli/roadmap/run.py`, and build the partials of `service_jobs` from `lane_specs`, so the job and the metadata of a lane cannot drift; the clone directory stays `lane_clone_dirname(lane)`. Add the `lanes` parameter to `create_service_app` in `src/devops_cli/server/service.py` and set `app.state.lanes` beside `app.state.jobs`. In `src/devops_cli/commands/serve.py`, pass `lane_specs(settings.service.lanes)` to `create_service_app`. Add the case for `lane_specs` in `tests/roadmap/test_roadmap_run_lane_table.py`, and rewrite `test_service_wiring` to read the table and the clone directory of each `LaneSpec` in place of the `run_due_jobs` patch
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lane_table.py tests/roadmap/test_roadmap_run_service.py` passes

## 4. Let the roadmap run command take the due table of its round

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/invariants/test_source_tree.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_roadmap_plan_check_cmd.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`, `tests/commands/test_roadmap_registries.py`, `tests/github/test_gh_issues_milestones_labels_runs_dry_run.py`, `tests/roadmap/implement/test_roadmap_implement_outside.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`. Changes: `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/invariants/test_source_tree.py`.
Adds: `run_roadmap_command`

- [ ] 4.1 `test_the_cli_prints_a_markup_error_of_a_failing_row` in `tests/roadmap/test_roadmap_run_due_table.py`: the case that patches `devops_cli.roadmap.run.run_due_jobs` at line 420 is rewritten to call `run_roadmap_command` with a stub table whose intake row raises `RoadmapRunError` with the text `[bold red]markup[/bold red]`, and it exits 1 with that literal text in its output
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/invariants/test_source_tree.py` fails on the base
- [ ] 4.2 Move the body of the `roadmap run` command in `src/devops_cli/commands/roadmap.py` into `run_roadmap_command`, which takes `table: Sequence[JobRow] | None = None` and passes it to `run_due_jobs`; the Typer command opens the store and calls it with no table. Rewrite the case in `tests/roadmap/test_roadmap_run_due_table.py` to call `run_roadmap_command` with a stub table and drop the patch of `run_due_jobs`. Lower `_INTERNAL_PATCH_CEILING` in `tests/invariants/test_source_tree.py` to 375, two below the staged 377, and stop when the run of that module reports a count that is not two below the staged value
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/invariants/test_source_tree.py` passes

## 5. Add the two devops ci cache cases over the git fake

Kind: other. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/ci/cache.py`, `tests/ci/test_ci_cache.py`, `tests/support/fakes/git.py`, `tests/support/fakes/process.py`. Changes: `tests/ci/test_ci_cache.py`.

- [ ] 5.1 Add `test_a_forced_run_ignores_a_matching_cache_entry` and `test_a_tree_that_changes_during_the_run_prints_the_warning` in `tests/ci/test_ci_cache.py`, beside `test_ci_cli_uses_the_cache_of_the_tree_it_fingerprints`, with the `isolated_cache_dir`, `tmp_path`, `monkeypatch` and `cli` fixtures and `git_fake` alone, which is a `ProcessFake` that answers a non-git program from its scripted answers. Request no second process fixture, because `git_fake` and `process_fake` both install the process runner and the second replaces the first. Build the tree and the index with `_FingerprintGitRepo`, and script the answer of each check that the run starts with `git_fake.answer`. The forced case writes a matching entry, runs `cli("ci", "--cache", "--force")` with no `--only`, and asserts that no cache-hit line prints and that the calls of the fake hold the check commands that ran. The second case scripts one check with a callable that rewrites a tracked file and then answers 0, and asserts the warning of `MESSAGES.ci.cache_tree_changed` and the entry that the cache file kept
  - Verification: `$ uv run devops ci test tests/ci/test_ci_cache.py` passes

## 6. Document the two seams in the testing page

Kind: other. Reads: `docs/TESTING.md`, `src/devops_cli/server/start.py`. Changes: `docs/TESTING.md`.

- [ ] 6.1 Add the server start seam and the lane metadata to the vocabulary and the fakes of `docs/TESTING.md`, beside the exporter seam, and name `src/devops_cli/server/start.py` and the lane metadata on the app state as the places that hold them
  - Verification: `$ uv run devops ci docs` passes
- [ ] 6.2 Edit `docs/TESTING.md` to name the server start fake and the lane metadata on the app state
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
