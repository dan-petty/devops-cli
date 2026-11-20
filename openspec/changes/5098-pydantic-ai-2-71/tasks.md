# Tasks

## 1. Pins

- [x] 1.1 Pin pydantic-ai 2.71.0 and pydantic-ai-harness 0.71.0, and lock
  - Verification: `$ uv lock --check`
- [x] 1.2 Remove the google-genai hold of the Renovate config
  - Verification: `$ npx --yes --package renovate@44.239.1 renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json`

## 2. Behavior

- [x] 2.1 Write the failing tests: retry parts from a recorded run, `answered_by`, the 408 frame, and a step that goes on after a file tool spends its retries
  - Verification: `$ uv run devops ci test tests/ai tests/roadmap/stage tests/roadmap/implement tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py`
- [x] 2.2 Find retries with `is_retry`, pass `answered_by`, send a 408 frame again, and import `FileSystem` from `file_system`
  - Verification: `$ uv run devops ci test tests/ai tests/roadmap/stage tests/roadmap/implement tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py`
- [x] 2.3 Remove every name of `RetryPromptPart` from the code and the tests, and ban it and `pydantic_ai_harness.filesystem` with the ruff rule TID251
  - Verification: `$ uv run ruff check --select TID251 src tests`

## 3. Documents

- [x] 3.1 Update the knowledge base pages of pydantic-ai and pydantic-ai-harness to 2.71 and 0.71
  - Verification: `$ uv run devops ci test tests/ai/test_kb.py`

## Workflow follow-up

- The last-retries line of `ToolCallLog` (#2866) shows only when no `Coder` answers the spent retries. The stock `Coder` item of #6519 decides it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
