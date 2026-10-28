# Tasks

## 1. Each provider gets the constraint that its model's profile supports

- [x] Add failing request-body tests: the `openai` provider gets the `response_format` of its model's pydantic-ai profile, `copilot` gets none, and `claude` gets `output_config.format` for a model that its profile names (with and without adaptive thinking) and none for a model that it does not name
  - Verification: `uv run devops ci test tests/test_ai_client_structured.py`
- [x] Give `ReplySchema` the OpenAI and Anthropic forms from the pydantic-ai profiles and transformers, send them from `_prepare_params` and `_build_anthropic_kwargs`, and delete the gateway-only branch of `_prepare_params`
  - Verification: `uv run devops ci test tests/test_ai_client_structured.py tests/test_thinking_providers.py tests/test_ai_chat_reply_stream.py`
- [x] Say in the docstring of `chat_structured` and in the knowledge-base page `devops_cli/libraries/pydantic_ai.md` which constraint each provider gets, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1419-structured-reply-constraint`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
