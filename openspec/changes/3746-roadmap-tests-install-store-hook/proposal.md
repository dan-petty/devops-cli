# Proposal

## Why

Issue #3746 is part 2 of 6 of #1335. Roadmap tests replaced `get_roadmap_store` with a patch of a module attribute, and the docstrings of `roadmap/__init__.py` and `get_roadmap_store` said that every caller looks the function up through its module "so that a test can patch it". ADR 0007 and `docs/TESTING.md` forbid a module that is shaped so that a test can patch it. A fake gets into the process through a seam that the source tree owns. The telemetry package already does this with `install_exporter` and `remove_exporter`.

The nine files of #3746 also patched other `devops_cli` names and imported private names: the model builders, the rate limiter, the adapters of the due table, the MCP runner and the CI cache helper. Each of these edges has a shared fake today, so the tests can use the fake in place of the patch.

## What Changes

- `roadmap/store.py` gets `install_roadmap_store(factory)` and `reset_roadmap_store()`. `get_roadmap_store(repo, runner=...)` returns `factory(repo, runner=runner)` when a factory is installed, else the GitHub store. The floor calls `reset_roadmap_store` after each test (`tests/conftest.py`, the table of process-wide state). The docstrings of `roadmap/__init__.py` and `get_roadmap_store` no longer say that a test patches the function.
- `ci/cache.py` gets `record_passing_run(...)` and `CacheRecord`. They hold the rule that a passing run is recorded only when the tree did not change while it ran. `commands/ci.py` `_try_save_ci_cache` calls it and prints the warning. This keeps the behavior and gives the rule a public function that a test can call.
- Tests, `tests/support/`:
  - The `roadmap_store` and `unreadable_github_roadmap` fixtures install their store through the hook. The session-wide refusal of the GitHub store (`github_roadmap_factory`) is deleted: the floor already refuses `gh`.
  - `tests/roadmap_github_fake.py` moves to `tests/support/fakes/github_repository.py`. `GitHubFake.install(process_fake)` answers the `gh` commands of a process fake as that repository.
  - `InMemoryRoadmapStore` gets `fail_write(error=...)`, `fail_read(...)` and `reads`. `ModelFake` accepts a function as an answer, and `chat_structured` raises `StructuredOutputValidationError` for a reply the schema refuses, as the real client does.
  - `tests/support/roadmap_jobs.py` gives `due_job_runner(name)`: the runner of a row of the due table, so no test imports a private adapter.
- Tests, the nine files of #3746: `test_roadmap_refine.py`, `test_roadmap_dry_runs.py`, `test_roadmap_intake.py`, `test_roadmap_run.py`, `test_roadmap_github_store.py` and `test_ci_cache.py` use the hook and the fakes. They hold no private import. They hold 4 patch sites more than the 5 seam sites of `test_roadmap_dry_runs.py`, see Feasibility.
- New tests: `tests/roadmap/test_roadmap_store_install.py` (the hook and the floor), `tests/roadmap/test_roadmap_store_fake.py` (the new faults of the fake) and two cases in `tests/ai/client/test_model_contract.py`.
- Not changed: the four largest roadmap test files stay whole (part 3 splits them). `tests/commands/test_github_milestones.py` keeps its other 6 patch sites.
- No command, option, message or request changes. The change has no spec delta, and `skip_specs: true` is set.

## Impact

- `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/__init__.py`, `src/devops_cli/ci/cache.py`, `src/devops_cli/commands/ci.py`.
- `tests/conftest.py`, `tests/support/` (`roadmap.py`, `roadmap_jobs.py`, `fakes/roadmap_store.py`, `fakes/github_repository.py`, `fakes/model.py`), `tests/roadmap/`, `tests/ci/test_ci_cache.py`, `tests/commands/test_github_milestones.py`, `tests/github/test_github_metrics.py` (import line), `tests/ai/client/test_model_contract.py`.
- `docs/TESTING.md` and the active plan `openspec/changes/3187-group-the-job-modules-in-subpackages/tasks.md` (one path).

## Feasibility

Checked on `origin/main` 5bc50d0a, 2026-11-06. The counts of #3746 were measured again with an AST pass: the nine files held 73 patch sites (5 seam sites) and 6 private imports, the tracker said 7. The premise holds for most sites. Four sites cannot move without a seam that another item owns, so they stay and the change does not hide them:

- `patch("uvicorn.run")` twice in `test_roadmap_run.py`. `devops serve` starts the ASGI server with `uvicorn.run`, and no seam lets a test see the app it gets. `tests/server/test_server.py` patches the same name five times, so one seam serves both. No fake exists for it yet.
- `patch("devops_cli.roadmap.run.run_due_jobs")` twice in `test_roadmap_run.py`. One case reads the lane jobs that `devops serve --service` builds. The other reads how the `run` command prints a `RoadmapRunError` whose text holds markup. No real job fails with such a text, and the lane table has no injection point.
- The `--force` half of `test_ci_cli_cache_hit_and_force` is removed, not moved. It patched `_run_all_checks_async` so that `devops ci --force` ran no check. `run_subprocess_async` does not use the process runner seam: it starts real child processes, and it reroutes to the sync path only when `subprocess.run` is patched (`core/process.py`, `run_subprocess_async`). #1333 owns that accommodation. Until it lands, no fake can answer the checks of `devops ci`. No other test covers `--force` with a cache hit.

The floor still refuses a real `gh` when a test opens the real store: `test_the_floor_fails_a_test_that_opens_the_github_store_and_runs_gh` shows it.

## Existing Tool Considered

`pytest` fixtures and `monkeypatch` are the usual tools, and ADR 0007 forbids `monkeypatch` on a `devops_cli` name. No open library gives an install hook for one function of this repository. The hook is 20 lines and follows `install_exporter`. The tests use the fakes that exist in `tests/support/fakes/`.
