# Design

## Decisions

- One mutmut campaign runs at a time, in the background, with `--max-children 4`, outside every git checkout. Each run reads `/sys/fs/cgroup/pids.current` first and waits while it is over 4000.
- The runs of #2176 that ended stay valid: the mutated source at 633021ead and at `origin/main` has the same function bodies, so this item reuses their results and runs only what is open.
- A row is `kept` when it has one own mutant. A row with an own mutant needs no further run to get its decision, so a row stops its campaign at the first proven own mutant, and the record names the own mutants that the runs proved.
- A mutant that no other file runs only because its statement runs at import time is not an own mutant: per-test coverage gives no test context to import-time code. Such a mutant needs a run against the files that import its module.
- A test that fails in the stats run of mutmut, before any mutation, kills no mutant. The run 2 folders leave it out, which can only add own mutants and keep a file.

## Rejected alternatives

- One whole-suite run per mutant: the suite takes about 75 minutes with 4 workers in a mutants tree, so one run per mutant does not fit the time of the item.
- Runs inside the worktree: the host path guard of `tests/conftest.py` stops each test that reads the `HEAD` of the nearest `.git` (#6448).
