# Proposal: #5606

## Why

The fix of #4472 counts the tests of a narrowed `devops ci test` run with a second pytest session, and chooses the workers from that count. Three defects stop it (#5606):

- A collection runs no test, so syrupy finds each snapshot of a selected module unused and exits 1. The command reads exit 1 as a failed collection and goes back to the file count. So the 7 modules of #4472 still run with `-n 0`.
- The run gives an explicit `-n 4`, and xdist reads `PYTEST_XDIST_AUTO_NUM_WORKERS` only for `-n auto` and `-n logical`. So a runner pod with 1 CPU runs 4 workers on that CPU.
- Each narrowed run starts the collection, also when its count cannot change the worker count, and the collection has the 1800 s timeout of the run.

## What Changes

- `_collection_cmd` in `src/devops_cli/commands/ci.py` adds `--snapshot-warn-unused`, the option that the shard rows already give, through one module constant `_SNAPSHOT_WARN_UNUSED`.
- A new `_worker_cap` gives `DEFAULT_CI_TEST_NARROWED_WORKERS`, or the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` when it is smaller. It ignores a value that is no whole number, as xdist does.
- `_narrowed_workers(targets, keyword)` starts the collection only when the count can change the answer. A cap of 1 or less runs `-n 0`. More than `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` target modules with no `-k` filter run on the cap. In all other cases the collection decides, and the file count decides when the collection gives no count.
- `DEFAULT_CI_TEST_COLLECTION_TIMEOUT_SECONDS` (120 s) joins `src/devops_cli/config/defaults.py` with the measured times in its comment, and the collection uses it.
- The warning of a failed collection prints with `safe=True`, so brackets in a target or a `-k` value print as text.
- `src/devops_cli/lang/en/help.py` adds the bound of `PYTEST_XDIST_AUTO_NUM_WORKERS` to the `-n` help, and `docs/commands/ci.md` is regenerated.
- `docs/TESTING.md` and `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md` state the new rule.
- `tests/commands/test_test_selection.py` adds the cases of #5606, puts the 12-module boundary back as a case of the fallback, and adds a `--repeat` case that makes no collection.
- The `-n` value that a run gets changes, so the change has a delta of `ci-test-workers`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-test-workers`: Collected tests choose the workers, Collection uses the run selection, Collection failure falls back (modified); Collection only when its count can change the workers, Repeat runs make no collection (added).

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/TESTING.md`, `docs/commands/ci.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md`
- Tests: `tests/commands/test_test_selection.py`
- A runner Job with 1 CPU runs a narrowed selection serially with no collection: a 52-test module took 37 s before and 8 s after on 1 CPU (`design.md`).

## Feasibility

- `git -C <worktree> log -1 origin/main` gave `b15faabb7 chore(main): release 0.136.1`, and `src/devops_cli/commands/ci.py:1941` on that commit is `def _collection_cmd(targets: list[str], keyword: str | None) -> list[str]:`, which returns `uv run pytest -n 0 --collect-only -q <targets>` with no syrupy option.
- `uv run pytest -n 0 --collect-only -q` on the 7 modules of #4472, with pytest 9.2.0, pytest-xdist 3.8.0 and syrupy 7.0.0, printed `4 snapshots unused.`, `Re-run pytest with --snapshot-update to delete unused snapshots.` and `422 tests collected in 1.03s`, and exited 1. The same command with `--snapshot-warn-unused` exited 0, and `collected_items` read 422 tests from its output. So the premise of defect 1 holds.
- `pytest_xdist_auto_num_workers` in the installed `xdist/plugin.py` reads `PYTEST_XDIST_AUTO_NUM_WORKERS` and ignores a value that `int()` refuses. xdist calls that hook only for `-n auto` and `-n logical`, and `_narrowed_workers` on `origin/main` returns the literal `str(DEFAULT_CI_TEST_NARROWED_WORKERS)`. With `PYTEST_XDIST_AUTO_NUM_WORKERS=1` and `taskset -c 3`, `uv run devops ci test tests/roadmap/test_roadmap_claim.py` printed `created: 4/4 workers`. So the premise of defect 2 holds.
- The same run took 37.2 s and 37.7 s, and `-n 0` on the same CPU took 7.9 s and 8.4 s. So the collection and the 4 workers cost about 29 s on 1 CPU, and the premise of defect 3 holds on this host.
- `_collected_test_count` on `origin/main` passes `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS` (1800 s) and calls `print_warning` with no `safe=True`. `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md:69` states the file-count rule. `tests/commands/test_test_selection.py` on `origin/main` has no 12-module case and no `--repeat` case. So the minor points of the issue hold.
- No newer issue or commit replaces this item: `git log origin/main` after 2126dc642 holds only release commits and #5594 with its revert #5601, which do not touch `src/devops_cli/commands/ci.py`.

## Existing Tool Considered

pytest-xdist is the open tool that starts the workers, and syrupy is the open tool that checks the snapshots. The fix uses the options that both give: `--snapshot-warn-unused` of syrupy, and `PYTEST_XDIST_AUTO_NUM_WORKERS`, the bound that xdist itself reads. No open tool chooses the workers of a narrowed run, so the change writes about 30 lines of policy in the command module. Cost: about 3,000 tokens to write, 3,000 tokens to keep and fix, and 3 hours of elapsed time. It deletes no internal code: it changes `_narrowed_workers` and keeps the fallback to the file count.
