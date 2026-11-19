# Design

## Decisions

- One mutmut campaign runs at a time, in the background, with `--max-children 4`, outside every git checkout. Each run reads `/sys/fs/cgroup/pids.current` first and waits while it is over 4000.
- The runs of #2176 that ended stay valid. Of the 59 mutable functions whose source changed between 633021ead and `origin/main`, no function is one that the 13 rows mutate. The runs mutate the tree of 633021ead, because the per-test coverage data gives the lines of that tree.
- A row is `kept` when it has one own mutant. A row with an own mutant needs no further run to get its decision, so a row stops its campaign at the first proven own mutant, and the record names the own mutants that the runs proved.
- Run 1 of a row first mutates only the functions whose body no other test file runs. A mutant that it kills is own with no run 2. A row with no such kill gets run 1 over each function whose body its file runs, as in #2176.
- A kill counts only when the row file alone kills the mutant again in a fresh pytest process outside every checkout. A kill inside mutmut can come from the state of its forked workers: the 16 `__getattr__` mutants of the settings cache row and the 9 timeout mutants of the style request row, which run 1 counted, pass the row file in a fresh process.
- A mutant that no other file runs only because its statement runs at import time is not an own mutant: per-test coverage gives no test context to import-time code. Such a mutant needs a run against the files that import its module.
- Run 2 leaves out the test files that `origin/main` deleted and the files of the rows of this wave that can still be deleted, so the decision of one row never rests on a file that another row removes.
- A test that fails in the stats run of mutmut, before any mutation, kills no mutant. The run 2 folders leave it out, which can only add own mutants and keep a file.

## Rejected alternatives

- One whole-suite run per mutant: the suite takes about 75 minutes with 4 workers in a mutants tree, so one run per mutant does not fit the time of the item.
- Runs inside the worktree: the host path guard of `tests/conftest.py` stops each test that reads the `HEAD` of the nearest `.git` (#6448).
- Trust each kill of mutmut: the fresh-process runs above show kills that the row file does not give again, so a row would stay with no check of its own.
