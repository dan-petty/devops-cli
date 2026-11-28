# Proposal: #7384

## Why
The Service opens plan pull requests in repositories that declare no `scope/spec` label with the title `docs: plan #<issue> <summary>`, because `open` strips undeclared scopes (`title_with_declared_scope`) (#7384). However, `is_plan_title_prefix` in `src/devops_cli/roadmap/pr_verdict.py` and `plan_check` in `src/devops_cli/roadmap/plan_check.py` only accept `docs(spec): plan` (or legacy `docs(openspec): plan`), so `devops pr ready` judges those plan PRs as implement drafts (failing on unticked tasks) and `devops roadmap plan-check` rejects their titles.

## What Changes
- Add `plan_title_prefix(has_spec_scope: bool) -> str` and `has_spec_scope(declared)` to `src/devops_cli/roadmap/pr_verdict.py`, update `is_plan_title_prefix(title, *, has_spec_scope=True)` to match `plan_title_prefix(has_spec_scope)` (plus legacy `docs(openspec): plan`), and update `is_plan_title(title, *, has_spec_scope=None)`.
- Add `has_spec_scope: bool = True` to `kind_of` in `src/devops_cli/roadmap/implement/implement_pull.py`, and read `.github/labels.yml` from `store` in `read_draft` and `src/devops_cli/roadmap/stage/stage_ready.py`.
- Extract `plan_check_title_problem` in `src/devops_cli/roadmap/plan_check.py`, read `.github/labels.yml` from `--repo` (or local git base rev), add `.github/labels.yml` to `plan_check_requests`, and report the repository-specific prefix in `MESSAGES.roadmap`.
- Provide `stage_plan_title` (and `staging_title(..., has_spec_scope=True)`) in `src/devops_cli/roadmap/stage/stage_change.py`, and support `docs: plan #<n>` in `plan_summary` and `src/devops_cli/roadmap/grounding.py`.

## Capabilities
- `roadmap-plan-check`: Accepts `docs: plan #<issue> <summary>` when `scope/spec` is absent from `.github/labels.yml`.
- `pr-merge-readiness`: Classifies `docs: plan #<issue> <summary>` as `DraftKind.STAGE_PLAN` when `has_spec_scope` is `False`.
- `roadmap-stage/plan-text`: Builds stage plan titles from `plan_title_prefix(has_spec_scope)`.

## Impact
- `src/devops_cli/roadmap/pr_verdict.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`: Scope-aware plan title prefix across all consumers and tests.

## Feasibility
Verified against `src/devops_cli/roadmap/pr_verdict.py:90-106`, `src/devops_cli/roadmap/implement/implement_pull.py:98-124,331-334`, `src/devops_cli/roadmap/plan_check.py:93-100,245-260,570-662`, `src/devops_cli/roadmap/stage/stage_change.py:114-116,3607-3638`, and `src/devops_cli/roadmap/grounding.py:330`.

## Existing Tool Considered
Alternatives check on #7384 recorded `none`: generic commit linters cannot derive a plan title prefix from repository `.github/labels.yml` or feed `kind_of`, `plan_check`, and `stage_change` (~6k tokens, ~2 hours to build cleanly).
