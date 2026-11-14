# Tasks

## 1. Refuse an open change's plan as feasibility evidence

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 Add `proposal_evidence_problems` to `stage_change.py` and the `citation` gate, with the problem text in `RoadmapMessages`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` passes
- [x] 1.2 Add the prompt sentence beside the Feasibility rules
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [x] 1.3 Add the cases: an open change's proposal is refused, an archived change's plan is accepted, and the problem reaches the citation gate
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` passes

## 2. Run the gates

Kind: other. Reads: `tests/roadmap/`. Changes: none.

- [x] 2.1 Run the gate of the branch
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
  - Verification: `$ uv run devops ci docs` passes
