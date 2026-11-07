# Design

## Context

See proposal.md for the motivation and the scope (#4021, item 6 of the Fit note of #1333). The migration of the `devops ci` tests (#3769) and the GitHub identity of the floor are separate items.

## Decisions

### 1. The module function calls the active runner
- **Decision**: `run_subprocess_async` is `await get_process_runner().run_async(...)`, as `run_subprocess` is `get_process_runner().run(...)`. `DefaultProcessRunner.run_async` is the one real implementation, and `ProcessFake.run_async` answers the same call.
- **Why**: the module function held a copy of the runner body and chose the sync path when `subprocess.run` was not the stdlib function. A test that used `process_fake` could not answer it, so the check hid the gap.
- **Rejected**: keep the check and add a branch for the fake. It would add a second test detection to hide the first.
- **Dry run**: the runner returns the planned result, and the program does not start. The copy printed the command and then started it. The only caller, `commands/ci.py`, leaves a dry run before it starts a program, so no observed behavior changes.

### 2. The cache key holds no config path
- **Decision**: the key of `_config_layers` is the project config variable, the working directory and the trust of the tree. The global config path is read from `CONFIG_PATH` when the layers are read, and the stamp check still compares the file the cache read.
- **Why**: the floor sets `HOME` before devops-cli is imported, so the path is the same for the whole process. Only a test that rebound the name needed it in the key.
- **Rejected**: a function that returns the global config path at each call. No test needs a second path now, and `CONFIG_PATH` has more than ten readers in `config/`.

### 3. `install_own_source_dir` is a public seam
- **Decision**: `core/repo.py` keeps the installed directory in a module variable. `_own_source_dir()` returns it, else the directory that the package is imported from. `reset_own_source_dir` clears it, and the floor calls it after each test. `reset_repo_caches` keeps it, so a test that clears the caches in its middle stays in the floor's isolation.
- **Why**: "which repository is my own" depends on where the code runs from. A test cannot move the package, so it needs a way to say where it runs. A public install function with a reset in the floor is the pattern of the other seams.
- **Rejected**: an environment variable. It would be a setting of the product that only tests use.
- **Rejected**: change the working directory of every test, so that the checkout is never the start of a review. It changes every relative path in the suite.

### 4. The origin cache uses the reset that exists
- **Decision**: delete the hand-attached `cache_clear`. A test that changes a remote calls `reset_repo_caches`.
- **Rejected**: a second public function for the origin cache alone. `reset_repo_caches` is already in the floor's reset list, and a second name would split one reset in two.

### 5. Two reads of `PYTEST_CURRENT_TEST` stay for now
- **Decision**: the ceiling in `tests/invariants/test_source_tree.py` is 2, the reads in `_clean_coverage_artifacts`. A new read fails the check.
- **Why**: the tests that reach those reads run the gate in the real checkout. Without the reads, they delete the `.coverage.*` files of the run that is measuring them. A root of their own for these tests is the work of #3769.
