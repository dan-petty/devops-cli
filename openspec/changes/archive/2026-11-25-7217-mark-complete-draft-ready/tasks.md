# Tasks

## 1. Invariant test of the draft rule

Kind: other

- [x] 1.1 Add `test_the_draft_rule_marks_a_draft_ready_when_no_agent_work_remains` to `tests/invariants/test_agents_md.py`. It reads rule 6 of `AGENTS.md`, rule 6 of the generated `AGENTS.md`, `CONTRIBUTING.md` and the three copies of `devops-pr-ci/SKILL.md`, and it fails before the text changes.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`

## 2. Instructions

Kind: other

- [x] 2.1 Change rule 6 of `AGENTS.md` and of `src/devops_cli/templates/AGENTS.md.j2`, and regenerate the snapshot of `tests/roadmap/implement/test_roadmap_implement_step.py`, which holds the rendered template.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/commands/test_instruction_generator.py tests/roadmap/implement/test_roadmap_implement_step.py`
- [x] 2.2 Change "Drafts First" of `CONTRIBUTING.md`, step 6 of `devops-pr-ci/SKILL.md` in the three skill roots, and the apply guidance of `openspec/config.yaml`.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/invariants/test_skills.py`
- [x] 2.3 Run the document, OpenSpec and lint gates.
  - Verification: `$ uv run devops ci --check --only docs,openspec,lint`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
