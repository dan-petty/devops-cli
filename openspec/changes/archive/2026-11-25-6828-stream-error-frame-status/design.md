# Design

## Decisions
- Catch `openai.APIError` in `_openai_compat_stream` (`src/devops_cli/ai/client/openai.py:405-406`) and raise `self._map_openai_error(exc)`. Both `openai.APIStatusError` and `openai.APIConnectionError` inherit from `openai.APIError`, so `except openai.APIError as exc:` routes every OpenAI SDK error in `_openai_compat_stream` through `_map_openai_error`.
- Forward `status=status` into `AICredentialsError` inside `credentials_error` (`src/devops_cli/ai/client/models.py:200-220`) so 401 and 403 responses carry `error.status` alongside `AIKeySpendLimitError` and `_status_error`.

## Rejected alternatives
- Map SSE error frames inside `_consume_stream`: rejected because `_consume_stream` in `src/devops_cli/ai/client/openai.py:524` is a stream-frame iterator without provider configuration or `_status_error` credentials/spend-limit context.
- Catch `openai.APIError` in `unified.py:chat_stream`: rejected because it leaves provider calls on `OpenAICompatMixin` unmapped and duplicates error mapping already implemented in `_map_openai_error` (`openai.py:103-124`).
