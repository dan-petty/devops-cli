# Tasks

## 1. Count a test of a module only when it imports the module

Reads: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/core/import_graph.py`, `src/devops_cli/roadmap/plan_recheck.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_plan_recheck.py`. Changes: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/core/import_graph.py`, `src/devops_cli/roadmap/plan_recheck.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_paths.py`, write `test_the_record_holds_a_test_only_when_it_imports_the_module` first, as a table of the import forms and of the false cases of the refused replies: the path of the messages module in a string, the dotted name in a string, an import of another module of the package, the stem of a module of another package and an import for types only. Add `test_a_group_that_changes_the_messages_names_a_test_that_runs_them`, `test_a_module_whose_only_holder_is_no_test_of_it_is_exempt`, `test_a_tree_that_cannot_read_its_files_records_no_test` and `test_grep_at_reads_a_dotted_name_as_a_fixed_string`. They fail on the base, which counts `tests/commands/test_new.py` as a test of `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` fails on the base
- [x] 1.2 Add `known` to `build_import_graph`. In `src/devops_cli/roadmap/stage/stage_paths.py`, give `StagedTree` a `reader` and `text`, and make `record_module_tests` read the imports of each candidate test with `build_import_graph`: the module, each package above it whose `__init__.py` imports it, and each other changed module that imports it. Make `grep_at` search with `-F -w`. Give the tree of `src/devops_cli/roadmap/plan_recheck.py` a reader of the revision
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py tests/roadmap/test_roadmap_plan_recheck.py` passes

## 2. Read a caller only for a parameter that a task adds

Reads: `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`.

- [x] 2.1 In `tests/roadmap/stage/test_roadmap_stage_paths.py`, write `test_the_caller_check_reads_only_a_parameter_that_a_task_adds` first, as a table of the task texts of the refused replies: an enum member, a property, a model field, a name in the next clause or sentence and a test function read no function, and a parameter, a keyword and an argument of two functions do. Add `test_a_caller_is_a_file_that_calls_the_function` and `test_a_class_has_no_caller`. They fail on the base, which reads `FailureClass`, `skipped` and `_fix` as changed functions
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` fails on the base
- [x] 2.2 Narrow `changed_functions` to a clause that says parameter, argument or keyword, and add `calling_files`, which reads the calls with `ast`. Make `StagedTree.callers` give it the files that `git grep -F -w` finds under `src`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` passes

## 3. State the rules

Reads: `docs/roadmap/plan-check.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/plan-check.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 State the import rule of the test of a changed module and the parameter rule of the caller check in `docs/roadmap/plan-check.md` and `docs/ROADMAP_WORKFLOW.md`. Run `uv run devops roadmap eval stage --replay` on the base commit and on the change, and state both outputs and the count of the stored refusals that the change clears in a pull request comment
  - Verification: `$ uv run devops ci docs`
