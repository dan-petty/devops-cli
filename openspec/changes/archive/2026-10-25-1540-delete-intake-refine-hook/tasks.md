# Tasks

## 1. Tests

- [x] Add failing test in `tests/test_roadmap_run.py` for P0-Critical bug, P2 bug, finished card, and absence of direct refine hook call <!-- id: 0 -->
- [x] Remove obsolete hook tests in `tests/test_roadmap_refine.py` and switch `refine_item` calls to `plan_refine` and `apply_refine` <!-- id: 1 -->
- [x] Remove `refine=` parameter usage from `tests/test_roadmap_intake.py` <!-- id: 2 -->

## 2. Implementation

- [x] Remove refine hook functions and `refine` argument from `src/devops_cli/roadmap/intake.py` <!-- id: 3 -->
- [x] Remove `refine_item` and `RefineOutcome` from `src/devops_cli/roadmap/refine.py` <!-- id: 4 -->
- [x] Update `_places_critical_or_p0` and `_run_intake_adapter` in `src/devops_cli/roadmap/run.py` <!-- id: 5 -->

## 3. Verification

- [x] Verify `fail-to-pass` check run <!-- id: 6 -->
- [x] Run full CI quality checks <!-- id: 7 -->
