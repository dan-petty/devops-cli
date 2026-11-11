# Tasks

## 1. The pointer stub says how its tool gets AGENTS.md
kind: behavior

- [x] 1.1 In `tests/commands/test_instruction_generator.py`, add a test that a stub with an import line says that the line loads AGENTS.md into the context and not to read it again, and that a stub without one says "Read that file."
  - Verification: `$ uv run devops ci test tests/commands/test_instruction_generator.py`
- [x] 1.2 In `src/devops_cli/templates/pointer_stub.md.j2`, give the stub with an import line the sentence about the import, and keep "Read that file." for the stub without one. Write CLAUDE.md, GEMINI.md and .github/copilot-instructions.md again with `devops ai agents --template`.
  - Verification: `$ uv run devops ci test tests/commands/test_instruction_generator.py tests/invariants/test_agents_md.py`

## 2. AGENTS.md asks for small tool output
kind: behavior

- [x] 2.1 In `tests/invariants/test_agents_md.py`, add a test that the rule "Keep tool output small" names the search before a read, `git diff --stat`, `--jq`, `--limit`, a Loki `limit`, error lines, `file:line` and failed test IDs.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`
- [x] 2.2 Add rule 14 to AGENTS.md. Remove the command details that the owning documents already hold (rules 2, 5, 6 and 11, and the review row), so AGENTS.md stays within 6,500 characters.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/implement/test_roadmap_implement_prompt.py tests/ci/test_fail_to_pass.py`

## 3. Documents
kind: other

- [x] 3.1 State the two stub branches in `src/devops_cli/ai/knowledge_base/devops_cli/tasks/agent_instructions_scaffolding.md`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The briefs of the workflow scripts outside the repository say "rules 1 to 12" or "rules 1 to 13". They need "rules 1 to 14", and they can tell an agent in an old worktree to read `git diff HEAD origin/main -- AGENTS.md`. No file of the repository holds them.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
