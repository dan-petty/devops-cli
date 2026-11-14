# Tasks

## 1. Count the creates of earlier groups

Reads: `src/devops_cli/roadmap/plan_check.py`. Changes: the same file and `tests/roadmap/test_roadmap_plan_check.py`.

- [ ] 1.1 In `_size_problems`, add the `creates` of each group to a set after the group is judged, and allow a changed path in that set.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` passes
- [ ] 1.2 Add the test of a later group that changes the file of an earlier group.
  - Verification: the same test command passes
