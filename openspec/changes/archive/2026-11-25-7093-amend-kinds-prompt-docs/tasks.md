# Tasks

## 1. Prompt and workflow doc tests

Kind: other

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/invariants/test_roadmap_workflow_doc.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/invariants/test_roadmap_workflow_doc.py`.

- [x] 1.1 Add failing tests asserting `roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, and `docs/roadmap/implement.md` document `add_path` (with `header`) and `group`.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py tests/invariants/test_roadmap_workflow_doc.py`

## 2. Synchronize coder prompt and roadmap documentation

Kind: other

Reads: `src/devops_cli/roadmap/implement/implement_amend.py`, `openspec/specs/roadmap-plan-amendment/spec.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`.

- [x] 2.1 Update `src/devops_cli/ai/tasks/roadmap_implement_step.md` to document `add_path` (with `header` set to `Changes` or `Reads`) and `group` in its `plan-request` guidance.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py`
- [x] 2.2 Update `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md` to list `add_path` and `group` among deterministic `plan-request` amendment kinds.
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py && uv run devops ci docs && uv run devops ci fail-to-pass --base origin/main`
