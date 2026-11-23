# Tasks

## 1. Count a meta skip by a false when as checked

Kind: behavior. Reads: `src/devops_cli/infra/plan.py`. Changes: `src/devops_cli/infra/plan.py`, `tests/infra/test_plan.py`.

- [x] 1.1 Write failing tests in `tests/infra/test_plan.py` for meta end_host skip and conditional result false skip callback lines
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Update `_check_mode_caused` in `src/devops_cli/infra/plan.py` to treat false condition `skip_reason` values as checked
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py` passes

## 2. OpenSpec specification delta

Kind: other. Changes: `openspec/changes/6334-count-a-meta-skip-by-a/specs/infra-plan/spec.md`.

- [x] 2.1 Add modified requirement `Hidden diffs and unchecked tasks` in `specs/infra-plan/spec.md`
  - Verification: `$ uv run devops openspec check` passes
