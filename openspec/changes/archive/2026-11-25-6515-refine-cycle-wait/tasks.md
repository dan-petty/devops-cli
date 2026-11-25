# Tasks

## 1. Behavior

- [x] 1.1 Write failing cycle regression tests in `tests/roadmap/refine/test_roadmap_refine_cycle.py` (`reply_removes_edge`, `stale_cycle_wait_ends`, `guide`)
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_cycle.py`
- [x] 1.2 Update `src/devops_cli/roadmap/refine/refine.py` to evaluate cycle from proposal edges and clear stale `person` cycle waits, and advance `CONST_ROADMAP_REFINE_RULES_SINCE` in `src/devops_cli/config/constants.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/refine.md` to name the dependency cycle step, state that only an open dependency outside a cycle makes an item wait, and record the new `CONST_ROADMAP_REFINE_RULES_SINCE` timestamp
  - Verification: `$ uv run devops ci docs`
