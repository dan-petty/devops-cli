# Tasks

## 1. Behavior

- [ ] 1.1 Write failing tests for git grep timeout and pathspec exclusions in refine context
  - Verification: `$ uv run pytest tests/roadmap/refine/test_roadmap_refine_context.py`
- [ ] 1.2 Handle `subprocess.TimeoutExpired` and apply exclusions in `src/devops_cli/roadmap/refine/refine.py`
  - Verification: `$ uv run pytest tests/roadmap/refine/test_roadmap_refine_context.py`

## 2. Validation & Quality Gates

- [ ] 2.1 Validate OpenSpec change
  - Verification: `$ openspec validate 4878-slow-git-grep-stops-refine-context-collection --type change`
- [ ] 2.2 Run local CI quality gates
  - Verification: `$ uv run devops ci --only format,lint,openspec,docs,uv-check,lockfile,constructs,git`
