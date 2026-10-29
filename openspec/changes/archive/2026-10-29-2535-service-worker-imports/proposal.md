# Proposal

## Why

Issue #2535: the Service deadlocks on the Python 3.14 import lock when two worker lanes run the refine job at the same time. Each lane imports `devops_cli.roadmap.refine` inside `_run_refine_adapter`. That module imports `devops_cli.roadmap.refine_investigation`, which reads `pydantic_ai`. Two threads import `pydantic_ai` for the first time at the same time, and the import lock raises `_DeadlockError`. A command with two or more repositories hits this race.

## What Changes

- `src/devops_cli/roadmap/run.py` imports `devops_cli.roadmap.refine` at module level, and `_run_refine_adapter` imports it not. `devops serve` reads `run.py` in the main thread before it starts the worker threads, so the Service imports `pydantic_ai` in the main thread, and no two lanes import it for the first time at the same time.
- The import order of the Service is a service's behavior a consumer observes. The change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-service-worker-startup`: the order in which the Service imports a job's dependencies against the start of its worker threads.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/run.py` (the import of `devops_cli.roadmap.refine`).
- Documents: none. The command and its options change not, so `devops docs generate` writes no file.
- Tests: `tests/test_roadmap_run.py` (one test that the import is at module level, not inside the adapter).

## Feasibility

- On the base commit, `_run_refine_adapter` in `src/devops_cli/roadmap/run.py` imports `devops_cli.roadmap.refine` inside the function. `src/devops_cli/roadmap/refine.py` imports `devops_cli.roadmap.refine_investigation`, which imports `pydantic_ai`.
- `src/devops_cli/commands/serve.py` reads `devops_cli.roadmap.run` in the main thread, before it starts the worker threads. So a module-level import of `devops_cli.roadmap.refine` in `run.py` imports `pydantic_ai` in the main thread, before the lanes run.
- I ran `tests/test_roadmap_run.py::test_the_refine_import_is_at_module_level_not_lazy_in_the_adapter` on the base. It failed: the import was inside the adapter, and none was at module level. After the change it passed, and `pydantic_ai` is in `sys.modules` after a main-thread import of `devops_cli.roadmap.run`.

## Existing Tool Considered

The Python import system covers the need: an import at module level runs in the thread that first reads the module. The Service reads `run.py` in the main thread before it starts the worker threads, so the standard import order removes the race with no library. The change moves the one import of `devops_cli.roadmap.refine` from the body of `_run_refine_adapter` to the top of `run.py`, and deletes no other code.
