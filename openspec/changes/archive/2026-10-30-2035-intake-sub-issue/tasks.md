# Tasks

## 1. Store protocol and implementations

- [x] 1.1 Add `add_sub_issue` method to `RoadmapStore` protocol and write failing contract test in `tests/test_roadmap_store_contract.py`
- [x] 1.2 Implement `add_sub_issue` in `MemoryRoadmapStore` and `GitHubRoadmapStore`
- [x] 1.3 Add sub-issues route to `tests/roadmap_github_fake.py`

## 2. Intake sub-issue linking and dry-run plan

- [x] 2.1 Add failing tests in `tests/test_roadmap_intake.py` for intake with `--source` linking sub-issues and appearing in dry-run plan
- [x] 2.2 Update `IntakeDecision`, `_apply_placement`, `plan_intake`, and `dry_run_intake` to link sub-issues and list the write in the dry-run plan
- [x] 2.3 Update module docstring in `src/devops_cli/roadmap/intake.py`

## 3. Verification and checks

- [x] 3.1 Verify OpenSpec check passes
- [x] 3.2 Verify full test suite passes
