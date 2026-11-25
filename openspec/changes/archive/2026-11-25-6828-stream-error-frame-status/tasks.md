# Tasks

## 1. Behavior

- [x] 1.1 Write failing stream SSE error-frame tests (`tests/ai/client/test_ai_streaming.py`)
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_streaming.py`
- [x] 1.2 Route `openai.APIError` through `_map_openai_error` in `_openai_compat_stream` (`src/devops_cli/ai/client/openai.py`)
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_streaming.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec changes and project gates after implementation
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
