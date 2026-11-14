# Tasks

## 1. Hold a stage-change pull request to its eval evidence

Reads: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_merge_readiness.py`. Changes: the same files.

- [ ] 1.1 In `src/devops_cli/github/merge_readiness.py`, add `BlockerKind.STAGE_EVAL`, the trigger path set `STAGE_CHANGE_TRIGGER_PATHS`, and `stage_eval_problems(body)` for the replay form and the live form. Add `_judge_stage_eval` and call it from `assess_merge_readiness` after the changed files are read.
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py` passes
- [ ] 1.2 Add `MESSAGES.pr.stage_eval_evidence_missing` that names the pull request, the trigger path, the problem and the command.
  - Verification: the same test passes and the blocker text names the path
- [ ] 1.3 Add the tests: a stage change with no evidence blocks, a replay with two numbers passes, a live run with one model passes, and the four refused forms fail.
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py` passes
