# Tasks

## 1. Move the store modules into `stores/`

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`. Changes: `src/devops_cli/roadmap/stores/__init__.py` (new), `src/devops_cli/roadmap/stores/store.py` (new), `src/devops_cli/roadmap/stores/github_store.py` (new), `src/devops_cli/roadmap/stores/memory_store.py` (new).

- [ ] 1.1 Run `git mv src/devops_cli/roadmap/store.py src/devops_cli/roadmap/stores/store.py`, and the same for `github_store.py` and `memory_store.py`, so each file is a rename with no edit to its body. Add `src/devops_cli/roadmap/stores/__init__.py` with a one-line docstring and no import. Rewrite the import of `devops_cli.roadmap.store` in `memory_store.py`, in `github_store.py` and in each module of `src/` that imports it to `devops_cli.roadmap.stores.store`
  - Verification: `! git grep -n -F 'from devops_cli.roadmap.store import' src/` passes

## 2. Move the intake modules into `intake/`

Reads: `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/intake_model.py`, `src/devops_cli/roadmap/intake_requests.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/intake/__init__.py` (new), `src/devops_cli/roadmap/intake/intake.py` (new), `src/devops_cli/roadmap/intake/intake_model.py` (new), `src/devops_cli/roadmap/intake/intake_requests.py` (new).

- [ ] 2.1 Run `git mv` for `intake.py`, `intake_model.py` and `intake_requests.py` of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/intake/`. Add `src/devops_cli/roadmap/intake/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path, such as `from devops_cli.roadmap.intake.intake import Filer`
  - Verification: `! git grep -n -F 'from devops_cli.roadmap.intake_model import' src/` passes

## 3. Move the refine modules into `refine/`

Reads: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/refine/__init__.py` (new), `src/devops_cli/roadmap/refine/refine.py` (new), `src/devops_cli/roadmap/refine/refine_investigation.py` (new).

- [ ] 3.1 Run `git mv` for `refine.py` and `refine_investigation.py` of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/refine/`. Add `src/devops_cli/roadmap/refine/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path
  - Verification: `! git grep -n -F 'from devops_cli.roadmap.refine import' src/` passes

## 4. Move the stage modules into `stage/`

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_criteria.py`, `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/stage_tools.py`. Changes: `src/devops_cli/roadmap/stage/__init__.py` (new), `src/devops_cli/roadmap/stage/stage.py` (new), `src/devops_cli/roadmap/stage/stage_change.py` (new), `src/devops_cli/roadmap/stage/stage_criteria.py` (new), `src/devops_cli/roadmap/stage/stage_probe.py` (new), `src/devops_cli/roadmap/stage/stage_tools.py` (new).

- [ ] 4.1 Run `git mv` for `stage.py`, `stage_change.py`, `stage_criteria.py`, `stage_probe.py` and `stage_tools.py` of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/stage/`. Add `src/devops_cli/roadmap/stage/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path
  - Verification: `! git grep -n -F 'from devops_cli.roadmap.stage_change import' src/` passes

## 5. Move the implement modules into `implement/`

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/implement/__init__.py` (new), `src/devops_cli/roadmap/implement/implement.py` (new), `src/devops_cli/roadmap/implement/implement_step.py` (new).

- [ ] 5.1 Run `git mv` for `implement.py` and `implement_step.py` of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/implement/`. Add `src/devops_cli/roadmap/implement/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path
  - Verification: `! git grep -n -F 'from devops_cli.roadmap.implement_step import' src/` passes

## 6. Rewrite the imports of the modules that stay at the top level

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/claim.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/claim.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/request_plan.py`.

- [ ] 6.1 In each module that stays at the top level of `src/devops_cli/roadmap/`, rewrite every import of a moved module to its new path, such as `from devops_cli.roadmap.stores.store import RoadmapStore` and `from devops_cli.roadmap.refine.refine import ...`. Change no other line of these files
  - Verification: `uv run devops ci test tests/roadmap` passes

## 7. Rewrite the imports of the commands and of the other packages

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/github/issues.py`, `src/devops_cli/survey/intake.py`, `src/devops_cli/ai/research/mental_model.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/github/issues.py`, `src/devops_cli/survey/intake.py`, `src/devops_cli/ai/research/mental_model.py`.

- [ ] 7.1 Rewrite every import of a moved roadmap module in `src/devops_cli/commands/roadmap.py`, `src/devops_cli/github/issues.py`, `src/devops_cli/survey/intake.py`, `src/devops_cli/ai/research/mental_model.py` and each other module of `src/` that imports a moved module, to the new module path. Change no other line of these files
  - Verification: `! git grep -n -F 'from devops_cli.roadmap.store import' src/devops_cli/commands/` passes

## 8. Hold the layout with invariant tests

Reads: `src/devops_cli/roadmap/__init__.py`, `tests/invariants/test_source_tree.py`, `docs/TESTING.md`. Changes: `tests/invariants/test_source_tree.py`.

- [ ] 8.1 Add to `tests/invariants/test_source_tree.py` a test that lists the module names at the top level of `src/devops_cli/roadmap/` and of its subpackages and asserts that no top-level name starts with `intake`, `refine`, `stage` or `implement`, that each job subpackage holds a module, and that `stores/` holds `store.py`, `github_store.py` and `memory_store.py`. Add a test that searches the Python files of `src/` and `tests/` for an import that names `store`, `github_store`, `memory_store`, `intake`, `refine`, `stage` or `implement_step` as a direct child of `devops_cli.roadmap`, and asserts no match. Add a test that parses `src/devops_cli/roadmap/__init__.py` and asserts its body holds one docstring and no import, assignment, class or function
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py` passes

## 9. Rewrite the imports of the tests and move the roadmap test modules

Reads: `tests/roadmap/test_roadmap_intake.py`, `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_stage_job.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/support/roadmap.py`. Changes: `tests/roadmap/intake/test_roadmap_intake.py` (new), `tests/roadmap/refine/test_roadmap_refine.py` (new), `tests/roadmap/stage/test_roadmap_stage_job.py` (new), `tests/roadmap/implement/test_roadmap_implement_step.py` (new), `tests/roadmap/stores/test_roadmap_github_store.py` (new), `tests/support/roadmap.py`.

- [ ] 9.1 Run `git mv` for each test module of `tests/roadmap/` into the directory of the subpackage that holds the behaviour it checks: `intake/`, `refine/`, `stage/`, `implement/` or `stores/`. Rewrite each import of a moved roadmap module in the moved test modules and in `tests/support/roadmap.py` to the new module path. Change no assertion and no other line of these files
  - Verification: `uv run devops ci test tests/roadmap` passes

## 10. Document the roadmap package layout

Reads: `src/devops_cli/roadmap/__init__.py`, `docs/TESTING.md`. Changes: `docs/roadmap/README.md` (new).

- [ ] 10.1 Write `docs/roadmap/README.md` with one table row for each subpackage of `src/devops_cli/roadmap/` (`intake`, `refine`, `stage`, `implement`, `stores`) and the modules it holds, one line that says the package `__init__` holds a docstring and re-exports no name, and the mirror of each subpackage under `tests/roadmap/`
  - Verification: `uv run devops ci docs` passes
- [ ] 10.2 docs/roadmap/README.md, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
