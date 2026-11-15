# Tasks: #5414 fix(roadmap): the fix_plan row judges and logs each plan it leaves out

- [x] 1.1 Add spec scenarios for branch stop skipping and mode plan candidate evaluation
- [x] 1.2 Add `fix_plan_mode_plan` and `fix_plan_left_round` messages to `src/devops_cli/lang/en/messages.py`
- [x] 1.3 Move branch check rules into `select_fix_plan`, log branch stops at WARNING, and continue to next candidate
- [x] 1.4 Judge each candidate in mode `plan`, record left-out plans, and add left-out deduplicated logging
- [x] 1.5 Register `reset_left_out_log` in `tests/conftest.py`
- [x] 1.6 Implement tests in `tests/roadmap/steps/test_roadmap_fix_plan.py` for mode plan logging, branch stop skipping, and branch stop warning
- [x] 1.7 Run `devops ci fail-to-pass --base origin/main` and verify all checks pass
