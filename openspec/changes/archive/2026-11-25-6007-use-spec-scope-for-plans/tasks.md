# Tasks

## 1. Switch plan title and commit scope to `spec` while accepting merged history
Kind: behavior

- [x] 1.1 Write failing tests covering `docs(spec): plan #` generation, dual-prefix reading (`docs(spec): plan #` and `docs(openspec): plan #`) in `pr_verdict.pull_kind`, `implement_pull.kind_of`, `implement`, `grounding.plan_issue`, `stage_overlap`, `stage_change.plan_summary`, `plan_drift`, `plan_check`, `docs(spec):` commit messages (`split`, `amend`, `archive`, `scaffold`, fixture plan commit), and the `pr-title.yml` `plan-check` workflow expression.
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py`
- [x] 1.2 Update `STAGING_TYPE`, `PLAN_TITLE_PREFIX`, `is_plan_title`, `plan_summary`, `stage_overlap`, `grounding`, `plan_check`, `plan_drift`, `implement`, `implement_pull`, `implement_run`, `implement_eval_run`, `rebase.ARCHIVE_MESSAGE`, `stage_job_phases`, and `messages.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/roadmap/stage/test_roadmap_stage_title.py tests/roadmap/stage/test_roadmap_stage_drift.py tests/roadmap/test_roadmap_draft_readiness.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_grounding.py tests/roadmap/implement/test_roadmap_implement_eval_run.py`

## 2. Labels, workflow, persona rules, tests, and documentation
Kind: other

- [x] 2.1 Replace `scope/openspec` / `openspec` commit scope in `.github/labels.yml`, `.github/workflows/pr-title.yml`, `src/devops_cli/ai/personas/lens.toml`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_coder.md`, `CONTRIBUTING.md`, `CONTEXT.md`, `docs/`, and existing test fixtures; update `test_workflow_contracts.py` and `test_lens.py`; run `uv run devops docs generate`.
  - Verification: `$ uv run devops ci --check --only docs,actionlint,zizmor,openspec`

## Workflow follow-up
- Live rename of `scope/openspec` to `scope/spec` and retitling open plan pull requests wait on #6314 after release.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
