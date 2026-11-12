# Design

## Decisions

- **Keep `PYTHONPATH`, keep the other isolation.** The test must run the helper as plain Python with no pytest run, in the same import environment as the test process. `-I` also drops `PYTHONPATH`, which the Service image test job needs. `-P` and `-s` keep the two other parts of `-I` that matter here: no working directory on the import path, and no user site directory. The child's `HOME` stays in the test's temporary directory.
- **No change to the guard.** The guard works when pytest is importable, which is true in each environment that runs the tests. The failure was in the test's process start, not in the guard.
