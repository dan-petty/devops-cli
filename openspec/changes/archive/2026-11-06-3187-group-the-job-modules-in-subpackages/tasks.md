# Tasks

## 1. Move the store modules into `stores/`

Reads: `src/devops_cli/roadmap/`, `src/devops_cli/roadmap/__init__.py`. Changes: `src/devops_cli/roadmap/stores/` (new) and `src/devops_cli/roadmap/__init__.py`.

- [x] 1.1 Run `git mv` for `store.py` and `github_store.py` of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/stores/`. Add `src/devops_cli/roadmap/stores/__init__.py` with a one-line docstring and no import. Change the docstring of `src/devops_cli/roadmap/__init__.py` to name `devops_cli.roadmap.stores.store.get_roadmap_store`
  - Verification: `ls src/devops_cli/roadmap/stores/__init__.py src/devops_cli/roadmap/stores/store.py src/devops_cli/roadmap/stores/github_store.py` passes

## 2. Move the job modules into `intake/`, `refine/`, `stage/` and `implement/`

Reads: `src/devops_cli/roadmap/`. Changes: `src/devops_cli/roadmap/intake/`, `src/devops_cli/roadmap/refine/`, `src/devops_cli/roadmap/stage/` and `src/devops_cli/roadmap/implement/` (new), with one `__init__.py` in each.

- [x] 2.1 Run `git mv` for the 3 `intake*.py` modules into `src/devops_cli/roadmap/intake/`, the 3 `refine*.py` modules into `src/devops_cli/roadmap/refine/`, the 27 `stage*.py` modules into `src/devops_cli/roadmap/stage/` and the 25 `implement*.py` modules into `src/devops_cli/roadmap/implement/`. Add an `__init__.py` with a one-line docstring and no import to each folder
  - Verification: `ls src/devops_cli/roadmap/intake/__init__.py src/devops_cli/roadmap/refine/__init__.py src/devops_cli/roadmap/stage/__init__.py src/devops_cli/roadmap/implement/__init__.py` passes

## 3. Rewrite the imports and string targets in `src/`

Reads: `src/devops_cli/commands/`, `src/devops_cli/github/`, `src/devops_cli/survey/`, `src/devops_cli/ai/` and the modules of `src/devops_cli/roadmap/`. Changes: each module of `src/` that names a moved module, and the documents that name the path of a moved module.

- [x] 3.1 Rewrite every import and every string target of a moved module in `src/`, the documents and the Kubernetes files that name its path. Run `ruff check --select I --fix` so the import blocks stay sorted
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py`

## 4. Rewrite the imports and string targets in the tests

Reads: `tests/support/`, `tests/ai/`, `tests/commands/`, `tests/core/` and `tests/roadmap/`. Changes: each test module that names a moved module, and `tests/fixtures/roadmap_eval/stage/3331-a-plan-that-changes-a-check/`.

- [x] 4.1 Rewrite every import and every string target of a moved module in the test modules. Keep the sample paths of the stage plan-check tests and of the frozen golden cases, and move the paths of the case `3331-a-plan-that-changes-a-check` with the trigger paths of the plan check. Change no assertion
  - Verification: `uv run devops ci test tests/roadmap tests/commands tests/core`

## 5. Move the roadmap test modules and their snapshots into the mirror directories

Reads: `tests/roadmap/`. Changes: `tests/roadmap/intake/`, `tests/roadmap/refine/`, `tests/roadmap/stage/`, `tests/roadmap/implement/` and `tests/roadmap/stores/` (new).

- [x] 5.1 Run `git mv` for each test module of `tests/roadmap/` whose name starts with `test_roadmap_intake`, `test_roadmap_refine`, `test_roadmap_stage` or `test_roadmap_implement` into the directory of that job, and `test_roadmap_github_store.py` and `test_roadmap_store_contract.py` into `tests/roadmap/stores/`. Move the snapshot file of a moved test module into the `__snapshots__` folder beside it. Add an empty `__init__.py` to each new folder
  - Verification: `ls tests/roadmap/intake tests/roadmap/refine tests/roadmap/stage tests/roadmap/implement tests/roadmap/stores` passes

## 6. Hold the layout with invariant tests

Reads: `src/devops_cli/roadmap/__init__.py`, `tests/invariants/test_source_tree.py`, `docs/TESTING.md`. Changes: `tests/invariants/test_source_tree.py`.

- [x] 6.1 Add to `tests/invariants/test_source_tree.py` a test that no top-level roadmap module starts with a job name and that each job subpackage and `stores/` hold their modules, a test that each import of `devops_cli.roadmap` in `src/` and `tests/` resolves to a module file or package folder, a test that the package module holds only its docstring, a test that `git log --follow` reaches the history of `stores/store.py` and skips in a checkout with no full history, and a test that the test tree mirrors the subpackages with each snapshot file beside its test module
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py`

## 7. Document the roadmap package layout

Reads: `src/devops_cli/roadmap/__init__.py`, `docs/TESTING.md`. Changes: `docs/roadmap/package-layout.md` (new) and `docs/index.md`.

- [x] 7.1 Write `docs/roadmap/package-layout.md` with one table row for each subpackage of `src/devops_cli/roadmap/` (`intake`, `refine`, `stage`, `implement`, `stores`), the modules it holds and its test folder, and one line that says the package `__init__` holds a docstring and re-exports no name. Link the page from `docs/index.md`
  - Verification: `uv run devops ci docs`
