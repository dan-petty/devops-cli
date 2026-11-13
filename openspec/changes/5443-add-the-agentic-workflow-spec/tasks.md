# Tasks

## 1. Documents

- [x] 1.1 Write `docs/AGENTIC_WORKFLOWS.md` with the measured state of 2026-11-13, the method, the rules and the gap table
  - Verification: `$ uv run devops docs check`
- [x] 1.2 List the spec in `.nav.yml` and `docs/index.md`, link it from `docs/ROADMAP_WORKFLOW.md`, and change the tuning sentence of `docs/roadmap/job-success.md` and of the docstring of `src/devops_cli/roadmap/job_result.py`
  - Verification: `$ uv run devops ci --check --only lint,format,docs,openspec,domain`
- [x] 1.3 File each gap that no open issue covers with `devops roadmap intake`, add the term **Branch run** to `CONTEXT.md`, and give the live plans of `docs/ROADMAP_WORKFLOW.md` a window of 28 days
  - Verification: `$ uv run --group docs devops docs site build --strict`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
