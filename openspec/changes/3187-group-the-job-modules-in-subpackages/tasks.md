# Tasks

## 1. Move the store modules into `stores/`

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/__init__.py`. Changes: `src/devops_cli/roadmap/stores/__init__.py` (new), `src/devops_cli/roadmap/stores/store.py` (new), `src/devops_cli/roadmap/stores/github_store.py` (new), `src/devops_cli/roadmap/stores/memory_store.py` (new), `src/devops_cli/roadmap/__init__.py`.

- [ ] 1.1 Run `git mv src/devops_cli/roadmap/store.py src/devops_cli/roadmap/stores/store.py`, and the same for `github_store.py` and `memory_store.py`, so each file is a rename with no edit to its body. Add `src/devops_cli/roadmap/stores/__init__.py` with a one-line docstring and no import. Rewrite the import of `devops_cli.roadmap.store` in `memory_store.py`, in `github_store.py` and in each module of `src/` that imports it to `devops_cli.roadmap.stores.store`, and the same for the other two modules. Change the docstring of `src/devops_cli/roadmap/__init__.py` to name `devops_cli.roadmap.stores.store.get_roadmap_store`
  - Verification: `test -z "$(find src/devops_cli/roadmap -maxdepth 1 \( -name store.py -o -name github_store.py -o -name memory_store.py \) -print)" && test -d src/devops_cli/roadmap/stores`

## 2. Move the intake modules into `intake/`

Reads: `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/intake_model.py`, `src/devops_cli/roadmap/intake_requests.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/intake/__init__.py` (new), `src/devops_cli/roadmap/intake/intake.py` (new), `src/devops_cli/roadmap/intake/intake_model.py` (new), `src/devops_cli/roadmap/intake/intake_requests.py` (new).

- [ ] 2.1 Run `git mv` for `intake.py`, `intake_model.py` and `intake_requests.py` of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/intake/`. Add `src/devops_cli/roadmap/intake/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path, such as `from devops_cli.roadmap.intake.intake import Filer`
  - Verification: `test -z "$(find src/devops_cli/roadmap -maxdepth 1 -name 'intake*.py' -print)" && test -d src/devops_cli/roadmap/intake`

## 3. Move the refine modules into `refine/`

Reads: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/refine/__init__.py` (new), `src/devops_cli/roadmap/refine/refine.py` (new), `src/devops_cli/roadmap/refine/refine_investigation.py` (new).

- [ ] 3.1 Run `git mv` for `refine.py` and `refine_investigation.py` of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/refine/`. Add `src/devops_cli/roadmap/refine/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path
  - Verification: `test -z "$(find src/devops_cli/roadmap -maxdepth 1 -name 'refine*.py' -print)" && test -d src/devops_cli/roadmap/refine`

## 4. Move the stage modules into `stage/`

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_criteria.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_render.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_eval_score.py`, `src/devops_cli/roadmap/stage_filter.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_github.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/stage_references.py`, `src/devops_cli/roadmap/stage_specs.py`, `src/devops_cli/roadmap/stage_split.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/roadmap/stage_validate.py`, `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/stage_verify_eval.py`. Changes: `src/devops_cli/roadmap/stage/__init__.py` (new) and one file under `src/devops_cli/roadmap/stage/` for each of the 22 modules.

- [ ] 4.1 Run `git mv` for `stage.py` and the 21 other `stage*.py` modules of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/stage/`. Add `src/devops_cli/roadmap/stage/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path, such as `from devops_cli.roadmap.stage.stage_change import StageProposal`
  - Verification: `test -z "$(find src/devops_cli/roadmap -maxdepth 1 -name 'stage*.py' -print)" && test -d src/devops_cli/roadmap/stage`

## 5. Move the implement modules into `implement/`

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/implement_amend.py`, `src/devops_cli/roadmap/implement_deadline.py`, `src/devops_cli/roadmap/implement_eval.py`, `src/devops_cli/roadmap/implement_eval_properties.py`, `src/devops_cli/roadmap/implement_eval_run.py`, `src/devops_cli/roadmap/implement_hooks.py`, `src/devops_cli/roadmap/implement_output_cap.py`, `src/devops_cli/roadmap/implement_outside.py`, `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_scoped_ci.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_strays.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/implement_test_names.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_trace.py`. Changes: `src/devops_cli/roadmap/implement/__init__.py` (new) and one file under `src/devops_cli/roadmap/implement/` for each of the 20 modules.

- [ ] 5.1 Run `git mv` for `implement.py` and the 19 other `implement*.py` modules of `src/devops_cli/roadmap/` into `src/devops_cli/roadmap/implement/`. Add `src/devops_cli/roadmap/implement/__init__.py` with a one-line docstring and no import. Rewrite the import of each moved module inside the moved files and in each module of `src/` that imports it to its new path, such as `from devops_cli.roadmap.implement.implement_step import StepOutcome`
  - Verification: `test -z "$(find src/devops_cli/roadmap -maxdepth 1 -name 'implement*.py' -print)" && test -d src/devops_cli/roadmap/implement`

## 6. Prove that no old module path remains in `src/`

Reads: the 29 modules that stay at the top level of `src/devops_cli/roadmap/`, `src/devops_cli/commands/`, `src/devops_cli/github/`, `src/devops_cli/survey/` and `src/devops_cli/ai/`. Changes: each module of `src/` that still names an old path.

- [ ] 6.1 Rewrite every import and every string target of a moved module in each module of `src/` that still names the old path, such as `from devops_cli.roadmap import store as roadmap_store` and `from devops_cli.roadmap.store import get_roadmap_store`. Change no other line of these files
  - Verification: `! git grep -n -E 'devops_cli\.roadmap\.(store|github_store|memory_store)([^a-z_]|$)|devops_cli\.roadmap import (store|github_store|memory_store)([^a-z_]|$)|devops_cli\.roadmap\.(intake|refine|stage|implement)(_[a-z_]+)?([^a-z_]|$)|devops_cli\.roadmap import (intake|refine|stage|implement)(_[a-z_]+)?([^a-z_]|$)' src/`

## 7. Rewrite the imports and string targets of the tests outside `tests/roadmap/`

Reads: `tests/support/roadmap.py`, `tests/support/roadmap_implement.py`, `tests/support/roadmap_stage.py`, `tests/support/builders.py`, `tests/support/implement_step.py` and each other test module outside `tests/roadmap/` that names a moved module. Changes: each such test module.

- [ ] 7.1 Rewrite every import and every string target of a moved module in the test modules outside `tests/roadmap/`. Change no assertion and no other line of these files
  - Verification: `! git grep -n -E 'devops_cli\.roadmap\.(store|github_store|memory_store)([^a-z_]|$)|devops_cli\.roadmap import (store|github_store|memory_store)([^a-z_]|$)|devops_cli\.roadmap\.(intake|refine|stage|implement)(_[a-z_]+)?([^a-z_]|$)|devops_cli\.roadmap import (intake|refine|stage|implement)(_[a-z_]+)?([^a-z_]|$)' tests/ ':!tests/roadmap/'`

## 8. Move the roadmap test modules and their snapshots into the mirror directories

Reads: the test modules of `tests/roadmap/`, `tests/roadmap/__snapshots__/`. Changes: `tests/roadmap/intake/`, `tests/roadmap/refine/`, `tests/roadmap/stage/`, `tests/roadmap/implement/` and `tests/roadmap/stores/` (new), each test module under them and each snapshot file beside its test module.

- [ ] 8.1 Run `git mv` for each test module of `tests/roadmap/` whose name starts with `test_roadmap_intake`, `test_roadmap_refine`, `test_roadmap_stage` or `test_roadmap_implement` into the directory of the job that the name gives. Move `test_roadmap_github_store.py` and `test_roadmap_store_contract.py` into `tests/roadmap/stores/`. Move the snapshot file of a moved test module into the `__snapshots__` directory beside it. Leave a test of a top-level module at `tests/roadmap/`
  - Verification: `test -z "$(find tests/roadmap -maxdepth 1 \( -name 'test_roadmap_intake*.py' -o -name 'test_roadmap_refine*.py' -o -name 'test_roadmap_stage*.py' -o -name 'test_roadmap_implement*.py' -o -name 'test_roadmap_github_store.py' -o -name 'test_roadmap_store_contract.py' \) -print)"`
- [ ] 8.2 Rewrite every import and every string target of a moved module in the moved test modules. Change no assertion and no other line of these files
  - Verification: `! git grep -n -E 'devops_cli\.roadmap\.(store|github_store|memory_store)([^a-z_]|$)|devops_cli\.roadmap import (store|github_store|memory_store)([^a-z_]|$)|devops_cli\.roadmap\.(intake|refine|stage|implement)(_[a-z_]+)?([^a-z_]|$)|devops_cli\.roadmap import (intake|refine|stage|implement)(_[a-z_]+)?([^a-z_]|$)' tests/`
- [ ] 8.3 Run the roadmap tests and verify that the suite passes with the same assertions as on the base tree
  - Verification: `uv run devops ci test tests/roadmap`

## 9. Hold the layout with invariant tests

Reads: `src/devops_cli/roadmap/__init__.py`, `tests/invariants/test_source_tree.py`, `docs/TESTING.md`. Changes: `tests/invariants/test_source_tree.py`.

- [ ] 9.1 Add to `tests/invariants/test_source_tree.py` a test that lists the module names at the top level of `src/devops_cli/roadmap/` and of its subpackages and asserts that no top-level name starts with `intake`, `refine`, `stage` or `implement`, that each job subpackage holds a module, and that `stores/` holds `store.py`, `github_store.py` and `memory_store.py`. Add a test that searches the Python files of `src/` and `tests/` for an import, a `monkeypatch.setattr` path or a logger name that names a moved module as a direct child of `devops_cli.roadmap`, and asserts no match. Add a test that parses `src/devops_cli/roadmap/__init__.py` and asserts its body holds one docstring and no import, assignment, class or function
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py`

## 10. Document the roadmap package layout

Reads: `src/devops_cli/roadmap/__init__.py`, `docs/TESTING.md`. Changes: `docs/roadmap/README.md` (new), and the generated documentation that `devops docs generate --sync-readme` writes.

- [ ] 10.1 Write `docs/roadmap/README.md` with one table row for each subpackage of `src/devops_cli/roadmap/` (`intake`, `refine`, `stage`, `implement`, `stores`) and the modules it holds, one line that says the package `__init__` holds a docstring and re-exports no name, and the mirror of each subpackage under `tests/roadmap/`. Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Start the move only after the pull requests #3182, #3011, #3015, #3017 and #3019 merge, because they change the stage and refine files that this change moves.
