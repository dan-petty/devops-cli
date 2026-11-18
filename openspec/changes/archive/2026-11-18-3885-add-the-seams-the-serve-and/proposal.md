# Proposal

## Why

The serve and roadmap tests still patch `uvicorn.run` and `run_due_jobs`, because no seam lets a test see the ASGI app that `devops serve` starts or the lane table that a Service lane runs (#3885). A patch of `run_due_jobs` cannot show the Rich markup that a real failing row prints, and a patch of `uvicorn.run` cannot show the app that the command builds. Two `devops ci` cache cases are missing for the same reason: no process fake answers the checks of the command.

## What Changes

- Add `ServerStarter`, `StartCall`, `UvicornStarter`, `get_server_starter`, `install_server_starter` and `remove_server_starter` in `src/devops_cli/server/start.py`, with `FakeServerStarter` in `tests/support/fakes/server.py` and a contract test that serves one request on a loopback port.
- Make `FakeServerStarter.start` record the start call and build the app from the factory, so the app exists only inside the start and no case builds it outside the call that the command made.
- Start the ASGI server of `devops serve` through the installed starter, in the service branch and in the REST branch of `src/devops_cli/commands/serve.py`, and drop the `import uvicorn` of the command.
- Register `remove_server_starter` in `_PROCESS_STATE_RESETS` of `tests/conftest.py`, so an installed fake never reaches a later test.
- Rewrite the nine `uvicorn.run` patch sites to install `FakeServerStarter` and read the recorded start call: seven in `tests/server/test_server.py` and the two in `tests/roadmap/test_roadmap_run_service.py`.
- Rename the app-build case of `tests/server/test_server.py` to `test_serve_service_mode_hands_the_starter_an_app_factory_and_the_json_log_config`, which asserts the factory flag, the log config and the one app that the fake built.
- Add `LaneSpec` and `lane_specs` in `src/devops_cli/roadmap/run.py`, build the jobs of `service_jobs` from them, and set `app.state.lanes` in `create_service_app`.
- Rewrite `test_service_wiring` to read `app.state.lanes` through the app that the fake built, with no `run_due_jobs` patch.
- Move the body of `roadmap run` into `run_roadmap_command`, which takes the due table, and drive the markup case through it.
- Lower `_INTERNAL_PATCH_CEILING` in `tests/invariants/test_source_tree.py` by the two `devops_cli` patches that the change removes.
- Add the `devops ci --force` cache case and the tree-changed warning case in `tests/ci/test_ci_cache.py`, over `git_fake` alone, which answers the checks as it answers any other program.
- Document the server start seam and the lane metadata in `docs/TESTING.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `command-test-seams`: The serve command starts the server through an installed starter, The run command takes the due table of its round

### Modified Capabilities

- `roadmap-service-lanes`: The app state holds each lane's table and clone directory

## Impact

- Code: `src/devops_cli/server/start.py`, `src/devops_cli/commands/serve.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/commands/roadmap.py`
- Documents: `docs/TESTING.md`
- Tests: `tests/support/fakes/server.py`, `tests/server/test_server_start_seam.py`, `tests/conftest.py`, `tests/server/test_server.py`, `tests/roadmap/test_roadmap_run_service.py`, `tests/roadmap/test_roadmap_run_lane_table.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/invariants/test_source_tree.py`, `tests/ci/test_ci_cache.py`

## Feasibility

- The premise of the issue was confirmed against the staged tree: `search_code` for `patch("uvicorn.run"` returned nine patch sites, at `tests/server/test_server.py:302:with patch("uvicorn.run") as mock_uvicorn:` and lines 384, 409, 441, 474, 489 and 508 of that module, and at `tests/roadmap/test_roadmap_run_service.py:54:with patch("uvicorn.run") as mock_uvicorn:` and `tests/roadmap/test_roadmap_run_service.py:113:with patch("uvicorn.run") as mock_uvicorn:`.
- The probe reads: 'The path `tests/roadmap/test_roadmap_run.py` is no file of the staging commit. Commit 355fc141 2026-11-07 test(roadmap): the four largest roadmap test files split by behaviour (#4050) deleted or renamed it.' The patches that the issue names live now in `tests/roadmap/test_roadmap_run_service.py` and `tests/roadmap/test_roadmap_run_due_table.py`, so the plan changes those files and plans no code that compensates for the deleted one.
- The probe reads: 'The path `tests/server/test_server.py` is a file of the staging commit.'
- The probe reads: 'The path `uvicorn.run` is no file of the staging commit. No commit in the history deleted or renamed it.' `uvicorn.run` is a symbol of the uvicorn package and no path of this repository, so that probe does not apply to it.
- The review finding is a defect and the new plan corrects it: `tests/server/test_server.py:416:def test_serve_service_mode_builds_the_app_after_the_server_applies_its_logging(` read the warnings at the start through the side effect at `tests/server/test_server.py:441:with patch("uvicorn.run", side_effect=run) as mock_uvicorn:`, and a plan that let the test call the recorded factory afterwards would assert a warning that appears whenever the test calls it, whatever the command does. Group 1 now has `FakeServerStarter.start` build the app from a factory, and group 2 renames the case to `test_serve_service_mode_hands_the_starter_an_app_factory_and_the_json_log_config`, which asserts the recorded `factory` flag, the log config, the one app that the fake built and the warning in `caplog`.
- `read_file` of `src/devops_cli/commands/serve.py` lines 120 to 240 showed `src/devops_cli/commands/serve.py:162:uvicorn.run(` in the service branch over `partial(create_service_app, ...)` with `factory=True`, and `src/devops_cli/commands/serve.py:219:uvicorn.run("devops_cli.server.app:create_app", factory=True, **options)` in the reload branch, so the start has three call sites and no seam. The REST branch builds its app before the start and passes the app.
- `search_code` for `app.state.jobs = ` showed `src/devops_cli/server/service.py:1179:app.state.jobs = lane_jobs`, so the app state is where a test reads what the command built, and the plan sets `app.state.lanes` beside it.
- `read_file` of `src/devops_cli/roadmap/run.py` lines 2128 to 2175 showed `service_jobs` building each lane job with `src/devops_cli/roadmap/run.py:2152:table=rows,` and `src/devops_cli/roadmap/run.py:2118:clone_dirname=lane_clone_dirname(lane),` inside `src/devops_cli/roadmap/run.py:2148:for lane, rows in service_lanes(groups).items():`, so one source already holds what a lane job passes on. `src/devops_cli/roadmap/run.py` defines no `LaneSpec` and no `lane_specs`, so both are new.
- `read_file` of `tests/roadmap/test_roadmap_run_service.py` lines 30 to 125 showed `tests/roadmap/test_roadmap_run_service.py:54:with patch("uvicorn.run") as mock_uvicorn:` in `test_service_wiring` with `tests/roadmap/test_roadmap_run_service.py:59:with patch("devops_cli.roadmap.run.run_due_jobs") as mock_run:`, and `tests/roadmap/test_roadmap_run_service.py:113:with patch("uvicorn.run") as mock_uvicorn:` in the halt and budget case, which reads `mock_uvicorn.call_args[0][0]().state.service_manager`.
- `search_code` for `patch("devops_cli.roadmap.run.run_due_jobs"` returned two sites: `tests/roadmap/test_roadmap_run_service.py:59:with patch("devops_cli.roadmap.run.run_due_jobs") as mock_run:` and `tests/roadmap/test_roadmap_run_due_table.py:420:with patch("devops_cli.roadmap.run.run_due_jobs", side_effect=failing_adapter):`.
- `read_file` of `src/devops_cli/commands/roadmap.py` lines 600 to 670 showed `src/devops_cli/commands/roadmap.py:647:ran = run_due_jobs(target, store, batch={("poll", "", ""): 1}, dry_run=False)` and `src/devops_cli/commands/roadmap.py:651:print_error(str(exc), safe=True)` inside `src/devops_cli/commands/roadmap.py:def run_cmd`, so the command owns the exit code and the round takes no table of its own.
- `search_code` for `cache_tree_changed` showed `src/devops_cli/commands/ci.py:1524:print_warning(MESSAGES.ci.cache_tree_changed, safe=True)`, so the warning case has its seam.
- `search_code` for `_INTERNAL_PATCH_CEILING = ` showed `tests/invariants/test_source_tree.py:563:_INTERNAL_PATCH_CEILING = 377`. The change removes the two internal patch sites above and adds none, so the ceiling falls to 375, and the group stops when the run reports a count that is not two below the staged value.
- `search_code` for `set_process_runner(fake)` showed `tests/support/fakes/git.py:139:set_process_runner(fake)` and `tests/support/fakes/process.py:453:set_process_runner(fake)`, so both fixtures install the process runner and the second replaces the first; `GitFake` answers a non-git program from its scripted answers, so the two cache cases request `git_fake` alone.
- `read_file` of `tests/conftest.py` lines 70 to 100 showed `tests/conftest.py:79:_PROCESS_STATE_RESETS: dict[str, tuple[str, ...]] = {`, the map that resets a module of `src` after each test.
- `list_files` of `src/devops_cli/server` showed `__init__.py`, `app.py`, `counter_series.py`, `json_logs.py`, `routes` and `service.py`, so `src/devops_cli/server/start.py` is a new file.
- `search_code` for `def install_exporter` showed `src/devops_cli/telemetry/tracer.py:def install_exporter`, the install hook whose shape the server start seam takes.
- `search_code` for `class _FingerprintGitRepo` showed `tests/ci/test_ci_cache.py:35:class _FingerprintGitRepo:` and `tests/ci/test_ci_cache.py:364:def test_ci_cli_uses_the_cache_of_the_tree_it_fingerprints(`, the fixtures that the two new cache cases sit beside.
- `read_spec` of `roadmap-service-lanes` returned seven requirements, none of which names the app state, so `The app state holds each lane's table and clone directory` is a new requirement of that capability.
- `FakeServerStarter.start` and `lane_specs` need no checkout, no client and no network: the fake builds the app in process and `lane_specs` reads the settings it is given.
- `run_roadmap_command` needs a client of the store: the case gives it the `seeded_store` fake and a stub table, so it needs no checkout and no network. `run_due_jobs` needs a client of the store in the same way, which the round supplies.
- `UvicornStarter.start` and `UvicornStarter.config` need a network: the contract test binds a loopback port in the test process and connects to it, while the serve and roadmap cases install the fake starter, which starts nothing. `docs/TESTING.md:256:A test that checks a service that is down refuses it through` shows that a loopback port the test process binds itself is allowed, and no case of the plan connects to a port that it did not bind.
- The first checks against the real system are `uv run devops ci test tests/server/test_server_start_seam.py`, `uv run devops ci test tests/server/test_server.py tests/roadmap/test_roadmap_run_service.py`, `uv run devops ci test tests/roadmap/test_roadmap_run_lane_table.py tests/roadmap/test_roadmap_run_service.py`, `uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/invariants/test_source_tree.py`, `uv run devops ci test tests/ci/test_ci_cache.py` and `uv run devops ci docs`.
- Runner capability: every verify program is `uv run devops ci test <path>` or `uv run devops ci docs`, and `uv`, `devops` and `pytest` are runner tools of the image, so no program of the plan is `NOT_IN_RUNNER`; uvicorn starts in process as an installed library of the image. The pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`. The failure classes that a step repairs are `test`, `lint` and `types`, and a `premise_false` class returns the item.

## Existing Tool Considered

uvicorn stays the server, and no library covers a test seam for its start, so the change adds a protocol, a real `UvicornStarter` and an install hook in the shape of `src/devops_cli/telemetry/tracer.py:def install_exporter`. Cost: 6k tokens and 4 hours to build, and about 1k tokens a year to keep. It deletes no source module: it deletes nine `uvicorn.run` patch sites and two `run_due_jobs` patch sites.

## Dependencies

- PR #6041 changes `src/devops_cli/commands/roadmap.py`, which the roadmap command group also changes; the later branch rebases on the other.
