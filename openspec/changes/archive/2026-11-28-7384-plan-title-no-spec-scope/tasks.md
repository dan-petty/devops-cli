# Tasks

## 1. Support scope-selected plan title prefixes across roadmap helpers and callers

Kind: behavior.

Reads: `src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`.

Changes: `src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_pr_verdict.py`, `tests/roadmap/test_roadmap_draft_readiness.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/stage/test_roadmap_stage_title.py`.

- [x] 1.1 Write failing tests in `tests/roadmap/test_pr_verdict.py`, `tests/roadmap/test_roadmap_draft_readiness.py`, `tests/roadmap/test_roadmap_plan_check.py`, and `tests/roadmap/stage/test_roadmap_stage_title.py` covering `plan_title_prefix`, strict `is_plan_title_prefix`, `kind_of(..., has_spec_scope=...)`, `read_draft` without `scope/spec`, `plan_check_title_problem` / `plan_check` without `scope/spec`, and `stage_plan_title`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/roadmap/test_roadmap_draft_readiness.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/stage/test_roadmap_stage_title.py`
- [x] 1.2 Implement `plan_title_prefix`, strict `has_spec_scope` checks, `kind_of` & `read_draft` & `stage_ready` wiring, `plan_check_title_problem` & `.github/labels.yml` reading in `plan_check`, `stage_plan_title`, and `grounding`/`plan_summary` unscoped support.
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/roadmap/test_roadmap_draft_readiness.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/stage/test_roadmap_stage_title.py`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
