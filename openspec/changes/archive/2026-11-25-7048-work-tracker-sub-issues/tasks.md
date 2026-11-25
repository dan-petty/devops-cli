# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_return.py`, `tests/roadmap/test_roadmap_explain.py`, and `tests/roadmap/test_roadmap_dependencies.py` asserting that `tracker_work` extracts open sub-issues (with blocker state) and open related `#<number>` links, `plan_return` refuses trackers while naming open sub-issues/related issues, and `explain_item` / `render_explanation` lists them for trackers.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dependencies.py tests/roadmap/test_roadmap_return.py tests/roadmap/test_roadmap_explain.py`
- [x] 1.2 Implement `tracker_work` in `src/devops_cli/roadmap/dependencies.py`, add the `item.is_tracker` refusal in `src/devops_cli/roadmap/return_item.py`, and surface tracker open sub-issues and related open issues in `src/devops_cli/roadmap/explain.py` and `src/devops_cli/lang/en/messages.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dependencies.py tests/roadmap/test_roadmap_return.py tests/roadmap/test_roadmap_explain.py`

## 2. Documents

- [x] 2.1 Write failing invariant checks in `tests/invariants/test_agents_md.py` and `tests/invariants/test_skills.py` verifying that `AGENTS.md` Rule 2, `src/devops_cli/templates/AGENTS.md.j2`, and `devops-roadmap/SKILL.md` direct agents to work tracker sub-issues/related issues instead of returning trackers.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/invariants/test_skills.py`
- [x] 2.2 Update `AGENTS.md`, `src/devops_cli/templates/AGENTS.md.j2`, `tests/roadmap/implement/__snapshots__/test_roadmap_implement_step.ambr`, all three `devops-roadmap/SKILL.md` roots, `src/devops_cli/lang/en/help.py`, and `docs/ROADMAP_WORKFLOW.md`, then regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` via `uv run devops docs generate`.
  - Verification: `$ uv run devops ci docs`
