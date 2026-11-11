# Tasks

## 1. Accept a test helper group in the plan check

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/core/test_selection.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`.

- [ ] 1.1 Write `test_a_test_only_other_group_that_changes_a_test_helper_is_accepted` in `tests/roadmap/stage/test_roadmap_stage_content.py` first. It fails on the base because `_test_only_group_problems` of `src/devops_cli/roadmap/stage/stage_change.py` refuses a group that changes `tests/support/builders.py`. Add `test_a_test_only_other_group_that_names_only_a_test_file_path_is_refused`. Add `test_content_problems_accepts_the_helper_rules_own_proposal`: it builds this plan's own `StageProposal`, calls `content_problems` and asserts that it returns no problem. Keep `test_a_test_only_other_group_with_no_named_test_is_refused` as the conditional case
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` fails on the base
- [ ] 1.2 Import `is_test_module` from `src/devops_cli/core/test_selection.py` in `src/devops_cli/roadmap/stage/stage_change.py`. Make `_test_only_group_problems` refuse a group only when every changed path starts with `tests/` and is a test module. Run `uv run devops roadmap eval stage --replay` on the base commit and on the change. State the score before and after the change in the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
