# Proposal

## Why

Issue #2371 asks to cut the work that each xdist worker repeats. The test row runs in four shards, and each shard runs `-n logical` workers, 16 in all. `pytest-split` picks the tests of a shard in `pytest_collection_modifyitems`, after collection. So each of the 16 workers collects the whole suite (19,514 tests in 830 files) and then drops three quarters of it.

One full run on a 16-CPU host (2026-11-05, 19,074 tests) spent 31.8 s of CPU in the collection of each worker. Over 16 workers that is 508.9 s, which is 13.5% of the 3,769.5 s of CPU of the run. Worker start was 2.8% of the CPU, and a preload fixture gave 0%. So the first plan of this change, a preload fixture, cannot be built, and the largest repeated cost is collection.

## What Changes

- `devops ci --shard <n> --shards <total>` passes the paths of the test modules of its own shard to pytest, so a worker collects no file of another shard.
- A function in `src/devops_cli/commands/ci.py` deals the test modules to the shards, heaviest file first (by lines), to the shard with the fewest lines so far. A tie goes to the lower shard. It stores no data.
- The test row no longer passes `--splits`, `--group` and `--splitting-algorithm`.
- `pytest-split` is removed from `pyproject.toml` and `uv.lock`.
- The spec `ci-test-shards` changes through a delta: one MODIFIED and one ADDED requirement. The command is observable, so the change carries a delta.
- `docs/TESTING.md`, `docs/SDLC.md` and the comment of the `test-shard` job in `ci.yml` stop naming `pytest-split` as the tool that splits the shards.
- The change fits one pull request and depends on no other item.
- The coverage report (#2373) and the startup-import tests (#2369) are out of scope.

## Acceptance

- Partition, same split everywhere, and the command: tests in `tests/commands/test_ci_shard.py`, groups 1 and 2.
- Same tests as before, shorter collection, lower CPU, shard time and runner time: measured and recorded in a comment of the pull request, as the issue lists. See "Workflow follow-up" in `tasks.md`.
- `pytest-split` is gone from `pyproject.toml` and `uv.lock`, and `openspec validate` passes: group 3.

## Impact

- Code: `src/devops_cli/commands/ci.py` (`_resolve_pytest_cmd`, new `_shard_test_files`).
- Tests: `tests/commands/test_ci_shard.py`.
- Dependencies: `pyproject.toml`, `uv.lock`.
- Documents and workflow comment: `docs/TESTING.md`, `docs/SDLC.md`, `.github/workflows/ci.yml`.
- Spec: `openspec/specs/ci-test-shards/spec.md`, through the delta in this folder.

## Feasibility

Checked on 2026-11-06 at `origin/main` ffaea530, and against the measurements of the issue (origin/main 4a2d958e).

- `pytest-split` 0.11.0 selects after collection. `pytest_split/plugin.py` defines `pytest_collection_modifyitems` with `@hookimpl(trylast=True)`, printed with `inspect.getsource` from the locked environment. A worker has collected every file by then.
- The files that pytest collects and the files that `_directory_modules("tests", root)` returns are the same set: the symmetric difference is empty (issue, 2026-11-06).
- A quarter of the files collects in 19.1 s of CPU against 29.0 s for the whole suite (66%; 12 runs of a quarter, 3 of the whole, pinned with `taskset -c 0-3`, loaded host). So the saving is about 158 s of CPU in a run, which is about 4%, and 10 s to 15 s of wall time in each shard.
- Split by lines gave 4,834, 5,181, 4,971 and 4,528 tests per shard, the largest 6.2% above the mean. A split by file size gave 14.4%.
- The earlier plan of this folder (a preload fixture and a measurement of worker start) is false: `pydantic_ai`, `anthropic`, `kubernetes` and `textual` are in `sys.modules` after collection, and a fixture moves an import and cannot lower the total CPU time. The issue of 2026-11-05 measured worker start at 2.8% of the CPU.
- The CI speed on the runner cannot be tested on this host. The pull request measures it, as the acceptance criteria say.

## Existing Tool Considered

- **`pytest`** takes file paths as arguments and then collects only those files. This open tool does the work.
- **`pytest-split` 0.11.0** is in use. It selects after collection and has no file-level option. This change removes it.
- **`pytest-xdist`** stays (`-n logical --dist worksteal`). `--dist loadfile` and `loadgroup` change how collected tests go to workers, and every worker still collects all tests.
- **`pytest-test-groups` and `pytest-shard`** are rejected: the first runs a subset of the collected tests by its README (the source was not read), and the second splits by test case only.
- **A `pytest_ignore_collect` hook** also skips files before collection, but it needs a conftest plugin and a `--shard` option. A list of paths does the same with no plugin.
- Cost if built: about 30,000 tokens to build, about 2,000 tokens a year to keep, and about half a day elapsed. The new function is about 25 lines and replaces a dependency, so the net code is small.
- Internal code deleted: the three split options in `_resolve_pytest_cmd`, and the `pytest-split` dependency.
