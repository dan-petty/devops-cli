# Proposal: #6007

## Why
The title of each plan pull request starts with `docs(openspec): plan #<n>`, and the stage and implement jobs write scaffolding, split, amend, archive, and fixture commits with `docs(openspec): ...`. Replacing the `openspec` commit scope with `spec` (#6007) shortens every plan title and commit subject by four characters in pull request lists, `git log`, and release notes while keeping the `devops openspec` CLI command group, `openspec/` directory, and OpenSpec tool unchanged.

## What Changes
- **Observable CLI and workflow behavior (spec deltas included):**
  - Stage plan pull request titles (`STAGING_TYPE` in `src/devops_cli/roadmap/stage/stage_change.py`, `PLAN_TITLE_PREFIX` in `src/devops_cli/roadmap/pr_verdict.py`) and plan-check error text (`plan_check_title`) move to `docs(spec): plan #`.
  - Plan-title readers (`pr_verdict.pull_kind`, `implement_pull.kind_of`, `implement._pull_reason`, `stage_change.plan_summary`, `stage_overlap`, `grounding.plan_issue`, `plan_check.is_plan`, `plan_drift`) accept both `docs(spec): plan #` and legacy `docs(openspec): plan #` so merged history and pre-rollout open plans keep working.
  - Stage scaffold, implement split, amend, archive, and eval fixture plan commit subjects move from `docs(openspec):` to `docs(spec):`.
  - `.github/labels.yml` declares `scope/spec` in place of `scope/openspec`; `.github/workflows/pr-title.yml` replaces `openspec` with `spec` in `semantic-title` and matches both prefixes in `plan-check`.
  - Documentation, prompts (`src/devops_cli/ai/tasks/`), persona label rules (`lens.toml`), tests, and living specs are updated; this fits in one pull request (live label rename and PR retitling are deferred to #6314).

## Capabilities
### Modified Capabilities
- `pull-request-form`: Update plan title examples to `docs(spec): plan #`.
- `pr-grounding`: Accept both `docs(spec): plan #` and merged/open `docs(openspec): plan #` titles.
- `pr-merge-readiness`: Classify both `docs(spec): plan` and `docs(openspec): plan` stage plan titles on draft kind collision.
- `roadmap-implement-job/pull-request`: Use `scope/spec` and `docs(spec): archive` for new commits/drafts while reading both `docs(spec): plan #` and `docs(openspec): plan #` from history.
- `roadmap-implement-job/stops`: Use `docs(spec): amend the plan of group <n> (#N)`.
- `roadmap-job-grades`: Score both `docs(spec): plan #` and `docs(openspec): plan #` bot pull requests as stage plans.
- `roadmap-plan-check`: Expect `docs(spec): plan #<issue> <summary>` in new plan title checks while recognizing both prefixes as plans.
- `roadmap-retitle`: Use `docs(spec): plan #` in the Planned-item example.
- `roadmap-stage/context`: Recognize both `docs(spec)` and `docs(openspec)` plan pull requests in overlap detection.
- `roadmap-stage/plan-text`: Emit `docs(spec): plan #` in `staging_title` scenarios.
- `roadmap-stage/round`: Emit `docs(spec): plan #` and `scope/spec` for new staged drafts.

## Impact
- Stage and implement pull requests, git commit messages, GitHub labels configuration, CI workflows, roadmap/PR tests, prompts, and documentation.

## Feasibility
- Confirmed on `origin/main` via `git grep -n -E 'STAGING_TYPE|PLAN_TITLE_PREFIX|ARCHIVE_MESSAGE' src/devops_cli/` and `git grep -n 'docs\\?\(openspec\\?\)' src/`:
  - `STAGING_TYPE: Final[str] = "docs(openspec)"` in `src/devops_cli/roadmap/stage/stage_change.py:114`
  - `PLAN_TITLE_PREFIX: Final = "docs(openspec): plan #"` in `src/devops_cli/roadmap/pr_verdict.py:89`
  - `_PLAN_SCOPE: Final[str] = "openspec"` in `src/devops_cli/roadmap/stage/stage_overlap.py:34`
  - `_PLAN_TITLE_RE` in `src/devops_cli/roadmap/grounding.py:330`
  - `ARCHIVE_MESSAGE` in `src/devops_cli/roadmap/phases/rebase.py:41`
  - `scope/openspec` in `.github/labels.yml:124` and `openspec` in `.github/workflows/pr-title.yml:73,127`
- First checks against the real suite: `uv run pytest -n 0 tests/roadmap/test_pr_verdict.py tests/roadmap/stage/test_roadmap_stage_title.py tests/roadmap/test_roadmap_plan_check.py tests/invariants/test_workflow_contracts.py` and `uv run devops ci --check --only actionlint,zizmor,docs,openspec`.

## Existing Tool Considered
- The refined issue records `alternatives.verdict = not-applicable` (internal refactor). No external maintained tool covers renaming internal commit/title scope constants, regexes, workflows, and docs in this repository. Estimated in-house maintenance cost is ~20k tokens / ~45 minutes.
