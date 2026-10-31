# Tasks

## 1. Context lengths

- [x] Set `OLLAMA_CONTEXT_LENGTH` of `ollama-48gib` to 262144 and of `ollama-16gib` to 131072, and expect these values in the profile test
  - Verification: `uv run pytest tests/test_ai_gateway_render.py -n 0`
- [x] Render the gateway configuration and update the example in the profiles README
  - Verification: `uv run devops ai gateway render` shows no difference

## 2. Verification

- [x] Run the full CI quality checks
  - Verification: `uv run devops ci`
