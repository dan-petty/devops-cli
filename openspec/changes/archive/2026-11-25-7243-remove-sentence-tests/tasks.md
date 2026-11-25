# Tasks

## 1. Remove the sentence tests

Kind: other

- [x] 1.1 Remove the 195 test functions that hold a sentence, a phrase, a heading or a count of a real document, prompt, template or skill, with the helpers and the snapshot that only they used.
  - Verification: `$ uv run devops ci test tests/invariants tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/implement tests/commands/test_instruction_generator.py`
- [x] 1.2 Change the 7 tests of code that held one sentence of a prompt or a document, and make `tests/invariants/test_skills.py` one generic rule.
  - Verification: `$ uv run devops ci test tests/invariants/test_skills.py tests/review/test_review_group_analysis.py tests/ci/test_fail_to_pass.py tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_plan.py tests/ai/test_ai_client_style_request.py`

## 2. Documents and specs

Kind: other

- [x] 2.1 Correct `docs/TESTING.md` and `docs/ROADMAP_WORKFLOW.md`, and remove the duration records of the deleted files.
  - Verification: `$ uv run devops ci --check --only docs,test-tree,lint,format,typecheck`
- [x] 2.2 Give the five requirements that named a removed test a command as the proof of the scenario.
  - Verification: `$ uv run devops ci --check --only openspec`

## Workflow follow-up

- The rule of the stage check that asks for a prompt sentence test, and the other spec scenarios whose proof is a sentence test: #7246.
