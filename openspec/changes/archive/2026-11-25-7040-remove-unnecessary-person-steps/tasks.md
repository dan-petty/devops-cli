# Tasks

## 1. Prompt and instruction invariant tests

Kind: other

- [x] 1.1 Add an invariant test in `tests/invariants/test_agents_md.py` asserting that `AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, and `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md` drop the retired person-only restrictions on labels, milestones, and evaluation verdicts.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`
- [x] 1.2 Add a prompt test in `tests/roadmap/refine/test_roadmap_refine_proposal.py` asserting that `src/devops_cli/ai/tasks/roadmap_refine_reply.md` limits `person` questions to `a merge, a secret, a repository setting or a host` and omits `a review verdict` and `a milestone`.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_proposal.py`

## 2. Agent instructions, workflow docs, skills, and refine prompt

Kind: other

- [x] 2.1 Remove `records verdicts` and `plans milestones` from the `Only a person` paragraph of `AGENTS.md` and `CONTRIBUTING.md`, and remove unnecessary person-only restrictions across `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/roadmap/intake.md`, and `docs/roadmap/refine.md`.
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Update `src/devops_cli/ai/tasks/roadmap_refine_reply.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md`, and the matching skill copies under `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/`.
  - Verification: `$ uv run devops ci test tests/invariants/test_skills.py tests/invariants/test_agents_md.py tests/roadmap/refine/test_roadmap_refine_proposal.py`
- [x] 2.3 Verify all docs, OpenSpec, construct, and lint gates pass.
  - Verification: `$ uv run devops ci --check --only docs,openspec,constructs,lint`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
