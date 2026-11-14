# Tasks

## 1. Count the tests of a narrowed run only when the count can change the workers

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/implement/implement_size.py`, `tests/commands/test_test_selection.py`, `tests/support/fakes/process.py`, `tests/support/session_spawns.py`. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `docs/commands/ci.md`, `tests/commands/test_test_selection.py`.

- [x] 1.1 Write the failing cases first in `tests/commands/test_test_selection.py`: the 7 modules of #4472 with a collection that exits 1 without `--snapshot-warn-unused` and 0 with it run on `DEFAULT_CI_TEST_NARROWED_WORKERS` with no warning; `PYTEST_XDIST_AUTO_NUM_WORKERS` of 1 and 0 run `-n 0` with no collection, 2 runs `-n 2`, and 16 and a value that is no number run on 4; 51 target modules with no `-k` make no collection, and 50 modules or a `-k` filter collect; a failed collection with `-k noop[/x]` exits 0 and shows `noop[/x]`; the collection call gets `DEFAULT_CI_TEST_COLLECTION_TIMEOUT_SECONDS` as its timeout, and the timeout warning names it, both read through `defaults` in the body of the test; and the collection argv holds `--snapshot-warn-unused`. Add the fixture `no_worker_bound` to `pytestmark`, so a runner pod's bound does not reach the other cases
  - Verification: `$ uv run devops ci test tests/commands/test_test_selection.py` fails on the base
- [x] 1.2 Add `_SNAPSHOT_WARN_UNUSED` to `src/devops_cli/commands/ci.py` and give it to `_collection_cmd` and the shard command. Add `_worker_cap`, which bounds `DEFAULT_CI_TEST_NARROWED_WORKERS` with `PYTEST_XDIST_AUTO_NUM_WORKERS`, and give `_narrowed_workers(targets, keyword)` the two skips of the collection. Add `DEFAULT_CI_TEST_COLLECTION_TIMEOUT_SECONDS` (120 s) with the measured times to `src/devops_cli/config/defaults.py`, use it in `_collected_test_count`, and print its warning with `safe=True`. Add the bound to the `-n` help in `src/devops_cli/lang/en/help.py`, and regenerate `docs/commands/ci.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/commands/test_test_selection.py tests/commands/test_ci.py tests/commands/test_ci_repeat.py` passes

## 2. Put back the boundary and repeat cases

Kind: other. Reads: `tests/commands/test_test_selection.py`. Changes: `tests/commands/test_test_selection.py`.

- [x] 2.1 Parametrize `test_a_failed_collection_falls_back_to_the_file_count_with_a_warning` with 12 test modules, which run `-n 0`, and 13, which run on `DEFAULT_CI_TEST_NARROWED_WORKERS`. Add a `--repeat 2 --seed 1` case to `test_a_run_that_chooses_its_workers_by_other_means_makes_no_collection`
  - Verification: `$ uv run devops ci test tests/commands/test_test_selection.py` passes

## 3. State the rule in the documents

Kind: other. Reads: `docs/TESTING.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md`. Changes: `docs/TESTING.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md`.

- [x] 3.1 State the collection option, the worker cap, the two skips of the collection, its timeout and the text warning in `docs/TESTING.md`, and replace the file-count rule of `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md` with the collected-test rule
  - Verification: `$ uv run devops ci --check --only docs` passes

## Workflow follow-up

- The rule of 50 collected tests stays: a 52-test module of fast tests runs 2.5 times slower on 4 workers than serially on 16 CPUs (#5612).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
