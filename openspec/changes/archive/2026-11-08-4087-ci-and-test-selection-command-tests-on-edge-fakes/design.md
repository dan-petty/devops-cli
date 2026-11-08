# Design

## Context

See proposal.md for the motivation and the scope (#4087, group 3 of #3769). The other groups of #3769 (`k8s`; `pr`, `gh` and `repos`; and the remaining command tests) are separate changes.

## Decisions

### 1. A test that starts the gate runs in a root of its own
- **Decision**: `ci_root` makes `tmp_path/tree` with a `.git` directory and makes it the current directory. `devops ci` resolves its root from the current directory, so the gate cleans, caches and runs its programs there. With this fixture the two reads of `PYTEST_CURRENT_TEST` have no reason to stay.
- **Why it is enough**: the only caller of `_clean_coverage_artifacts` is the gate (`_run_all_checks_async`), and the proposal shows by a planted file that only the tests which start the gate in the repository root can reach the live files.
- **Rejected**: keep the check of `PYTEST_CURRENT_TEST` for the repository root. It is product code that changes when a test runs, which `docs/TESTING.md` forbids.
- **Rejected**: patch `_get_project_root` in each test. It is the patch this item removes.

### 2. The process fake answers a program by what the program would read
- **Decision**: `process_fake.answer` takes a predicate and a callable. A test that needs ruff to fail in one directory answers by `call.cwd`, and a test that needs a coverage database after pytest writes it in the answer. `ci_head` answers `git rev-parse HEAD`, so the gate takes a fingerprint, and every other git command succeeds with no output, which is a clean tree.
- **Rejected**: `GitFake` with transcripts for the gate tests. The tests need no real git behavior, only a commit and a clean tree, and `tracked_blobs` states the one case that needs files.

### 3. The cache is the real cache
- **Decision**: a test that needs a cache hit runs the gate once, so that the real `record_passing_run` writes the verdict, and runs it again. The test reads the verdict with `compute_workspace_fingerprint` and `get_ci_cache`, the public functions of `devops_cli.ci.cache`. The cache file sits in the data directory of the hermetic floor.
- **Rejected**: patch `_try_fast_cached_ci` and `_try_save_ci_cache`, as the old tests did. They proved that the command called a function, not that a verdict was kept or trusted.

### 4. The time of a check comes from the clock seam
- **Decision**: `_execute_check_async` calls `clock.monotonic()` where it called `time.perf_counter()`. The `clock` fixture moves that reading when the process fake sleeps, so a test gives a check any duration with `ProcessAnswer(delay=...)`.
- **Rejected**: patch `_warn_when_over_budget` and its printers, as the old budget tests did.
- **Not changed**: `_run_python_version_step` and the gate's total keep their readings. No test needs them.

### 5. The warnings about the checked tree are one public function
- **Decision**: `gate_root_warnings(root, mounts_text=None)` in `ci/diagnostics.py` returns the warning for a stale worktree and the warning for a slow host share. `_announce_gate_root` prints them. The test of the host share gives it the text of `/proc/mounts` that `slow_mount_fstype` already takes.
- **Rejected**: patch `slow_mount_fstype` or `_PROC_MOUNTS`. The first is a `devops_cli` name, and the second is a module constant that exists for the patch.
- **Rejected**: make the test depend on the filesystem of `tmp_path`. A test must give the same answer on every host.

### 6. The directory and shard functions are public in `core/test_selection.py`
- **Decision**: `directory_modules` (was `_directory_modules`) and `shard_test_files` (was `_shard_test_files`) hold no command logic: they read a tree and return paths. `core/test_selection.py` already holds `is_test_module` and the rest of the selection. The shard tests call them directly, and the rows of the plan show the command that uses them.
- **Rejected**: move all of the selection helpers of `commands/ci.py` (`_map_changed_paths` and its siblings). They print and exit, so they mix the domain with the command, and a split needs its own item. The tests reach them through `devops ci test`.

### 7. Dead parameters and functions go
- **Decision**: `_clean_coverage_artifacts(force=True)` and `_run_all_checks` have no caller in `src/`. Tests called them to avoid the clean-up guard and to run a gate without the CLI. The tests now age their files and call the CLI, so both go.

### 8. The tests that cannot observe a thing through the CLI say so
- The duration of the coverage row is observable as a dash in the summary, not as a sum. The test of `_assemble_ci_results` checked a sum that no command prints, and the dash is what the command promises.
- The two worktree lint tests used the real ruff. They answer ruff from the fake by directory, because a test of `src/` starts no system program (`docs/TESTING.md`).
- The test of the repair command for a moved worktree still runs `git status` in the repaired worktree through the fake, as before. The fake answers success, so the test checks that the warning names one repair command and that the files the test writes are the ones that command would write.
