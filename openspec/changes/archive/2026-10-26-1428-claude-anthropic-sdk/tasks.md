# Tasks

## 1. Dependencies and Model Presence Validation

- [x] 1.1 Write failing test asserting provider `claude` requires non-empty `ai.model` and raises `ConfigurationError` naming `ai.model` (`uv run devops ci test tests/test_claude_provider.py`)
- [x] 1.2 Add `anthropic==1.12.1` to `pyproject.toml` dependencies and enforce mandatory `ai.model` in `LLMClient._validate_resolved_config` (`uv run devops ci test tests/test_claude_provider.py`)
- [x] 1.3 Regenerate command documentation (`uv run devops docs generate --sync-readme`)

## 2. Capability Resolution and Adaptive Thinking Payloads

- [x] 2.1 Write failing tests in `tests/test_claude_provider.py` asserting capability retrieval via Models API, adaptive thinking payload generation without `budget_tokens`, and SDK client HTTP client identity (`uv run devops ci test tests/test_claude_provider.py`)
- [x] 2.2 Rebuild `ClaudeProviderMixin._claude_messages` on `anthropic.Anthropic` using `_shared_client()`, resolve model capabilities via Models API, format adaptive thinking with `output_config.effort`, and remove `budget_tokens` and name checks (`uv run devops ci test tests/test_claude_provider.py`)
- [x] 2.3 Regenerate command documentation (`uv run devops docs generate --sync-readme`)

## 3. Sampling Parity, Stream Modernization, and Cleanup

- [x] 3.1 Write failing tests in `tests/test_claude_provider.py` asserting sampling parameter parity between streamed and unstreamed requests when supported, and omission when unsupported (`uv run devops ci test tests/test_claude_provider.py`)
- [x] 3.2 Rebuild `_claude_stream` via `anthropic.Anthropic.messages.stream`, delete `_CLAUDE_EVENT_FRAMES` and `_claude_stream_frame` in `src/devops_cli/ai/client/streaming.py`, purge `claude-3-` mentions across `src`, and update obsolete test references (`uv run devops ci test tests/test_claude_provider.py tests/test_ai_streaming.py`)
- [x] 3.3 Validate the complete quality gate and static checks (`uv run devops ci`)

## Workflow follow-up

- Pending a person: `devops ai chat` with provider `claude` and a current model returns a reply.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
