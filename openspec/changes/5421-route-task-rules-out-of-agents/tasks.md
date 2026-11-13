# Tasks

## 1. AGENTS.md and its cap

- [x] 1.1 Write the test: the table routes a closed model question to the `ask-jev` skill, and the skill says to ask only when no file or deterministic check can answer
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`
- [x] 1.2 Rewrite `AGENTS.md`, add the two short additions to `SECURITY.md` and the `ask-jev` skill copies, and lower `CONST_AGENTS_MD_MAX_CHARS` and the test bound to 4,500
  - Verification: `$ uv run devops ci test tests/invariants tests/commands/test_instruction_generator.py tests/roadmap/test_roadmap_step_rules.py tests/roadmap/implement`
- [x] 1.3 Point the tests that read a moved sentence at its home, and align the cost words of `openspec/config.yaml` with the stage prompt
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/stage/test_roadmap_stage_cost_units.py`

## 2. Documents

- [x] 2.1 Cite `docs/TESTING.md` in `fail-to-pass.yml`, and change the model-kind requirement of the `agent-instructions` spec
  - Verification: `$ uv run devops ci --check --only lint,format,domain,docs,openspec`
