# Tasks

## 1. Behavior: the repair scope

- [x] 1.1 Add the failing tests: the scope holds the plan paths and the change folder, a log matches a path as a whole word, a check outside the scope stops the item with no model request, and a check on a plan path gets a fix turn
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_fix_scope.py tests/roadmap/implement/test_roadmap_implement_fix_scope_stop.py`
- [x] 1.2 Add `implement_fix_scope.py` and the check in `_repair_after_push`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_fix_scope.py tests/roadmap/implement/test_roadmap_implement_fix_scope_stop.py tests/core/test_roadmap_implement_checks.py tests/roadmap/implement/test_roadmap_implement_strays.py`

## 2. Documents

- [x] 2.1 State the stop in `docs/roadmap/implement.md`
  - Verification: `$ uv run devops ci docs`
