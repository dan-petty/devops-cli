# Tasks

## 1. Name the same-name file of a stale test path
kind: behavior

- [x] 1.1 Add two tests to `tests/roadmap/stage/test_roadmap_stage_form.py`: a changed docstring that names `tests/test_item_grounding.py` on a tree that holds `tests/github/test_item_grounding.py` gets a problem that ends with the text of `stage_path_same_name` for that file, and a stale path with no same-name file gets a problem that ends with `stage_path_no_same_name`. Both fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py`
- [x] 1.2 Add `same_name_hint` to `src/devops_cli/roadmap/stage/stage_paths.py` and call it from `_problem`. Add a `{hint}` placeholder to `stage_problem_missing_test_file` in `src/devops_cli/lang/en/messages.py`, and format it in `_stale_test_path_problems` of `src/devops_cli/roadmap/stage/stage_change.py` with `same_name_hint`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py tests/roadmap/stage/test_roadmap_stage_paths.py`
- [x] 1.3 Replay the recorded stage plans through the gates on the base and on the change, and compare the two reports.
  - Verification: `$ uv run devops roadmap eval stage --replay`
