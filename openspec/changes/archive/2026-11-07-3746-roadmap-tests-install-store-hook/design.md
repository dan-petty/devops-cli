# Design

## Context

See proposal.md for the motivation and the scope (#3746, part 2 of #1335). The in-memory store lives in `tests/support/fakes/roadmap_store.py` since part 1 (#3744).

## Decisions

### 1. One install hook, like the exporter
- **Decision**: `install_roadmap_store(factory)` sets a module variable, `reset_roadmap_store()` clears it, and `get_roadmap_store` reads it first. The floor registers the reset in `_PROCESS_STATE_RESETS`, so the invariant that checks module state in `src` passes.
- **Rejected**: keep the patch of the function. ADR 0007 forbids it.
- **Rejected**: a `contextvars` variable. A job thread of the Service would not see a value that the test thread set.

### 2. No session-wide refusal of the GitHub store
- **Decision**: delete `github_roadmap_factory`. A test that opens the real store runs `gh`, and the floor fails it with a message that names `gh`.
- **Rejected**: keep the refusal. It repeated a rule that the floor holds.

### 3. A rule that a command holds becomes a public function
- **Decision**: `record_passing_run` in `ci/cache.py` holds the rule "record a passing run only when the tree is the tree it started on". The command prints the warning. The test calls the public function over the git fake.
- **Rejected**: keep importing `_try_save_ci_cache` and patching `print_warning`.

### 4. Fakes get the faults the tests need
- **Decision**: the store fake gets `fail_write(error=...)`, `fail_read` and `reads` in place of `patch.object(store, ...)`. `ModelFake` accepts a function as an answer so that a test script can read the request, and it raises the client's validation error for a reply that the schema refuses. `GitHubFake.install` hangs the repository on a process fake in place of a patch of `subprocess.run`.
- **Rejected**: a subclass that overrides one method in each test.

### 5. Sites that need another item's seam stay
- **Decision**: the two `uvicorn.run` patches, the two `run_due_jobs` patches and the `--force` case are named in the proposal. They wait for a server seam and for #1333.
- **Rejected**: add a seam for the ASGI server here. It serves `tests/server/` too and is its own item.
