# Tasks

## 1. State the decided ways of working
kind: documents

- [x] 1.1 Put each decided rule into its owning document: `AGENTS.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/TESTING.md`, `k8s/README.md` and `CONTEXT.md`. Replace each copy with a link.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/invariants/test_roadmap_workflow_doc.py tests/core/test_docs_routine_tasks.py tests/invariants/test_roadmap_stage_measure_doc.py`

## 2. Correct the stale facts
kind: documents

- [x] 2.1 Correct the coverage floor, the nesting cap, the release merge, the trace and metrics text, the moved test paths, the Argo Workflows text, the Mattermost steps, the dashboard follow-ups and the Planned changes table.
  - Verification: `$ uv run devops ci docs`
