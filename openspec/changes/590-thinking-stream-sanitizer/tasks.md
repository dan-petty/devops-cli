# Tasks

## 1. Thinking-Stream Sanitizer Core and Profile Configuration

- [ ] 1.1 Write failing tests for unopened closing tag counting, EOF unclosed stream detection, thought buffer character capping, and initial state profile configuration (`uv run devops ci test tests/test_thinking.py tests/test_ai_streaming.py`)
- [ ] 1.2 Implement the unified ThinkingFSM core in `devops_cli.ai.thinking_stream` with unopened tag counting, EOF unclosed stream reporting, thought buffer character capping at 65,536 characters, and configurable initial state (`uv run devops ci test tests/test_thinking.py`)
- [ ] 1.3 Adapt `ThinkingStreamProcessor`, `StreamingTokenProcessor`, `strip_think_blocks`, and `extract_think_blocks` to delegate to the shared FSM core, expose `unopened_close_tags`, `unclosed_stream`, `discarded_thought_chars`, and delete `StreamingReasoningSanitizer` (`uv run devops ci test tests/test_ai_streaming.py`)
- [ ] 1.4 Add `_apply_profile_spec`, `get_model_thinking_tags`, and `supports_thinking` to `devops_cli.ai.profiles` and configure `initial_state` and `thinking_tags` resolution (`uv run devops ci test tests/test_thinking.py`)
- [ ] 1.5 Record `unopened_close_tags`, `unclosed_stream`, and `discarded_thought_chars` metrics on stream trace spans in `devops_cli.ai.client.unified` (`uv run devops ci test tests/test_ai_client_telemetry.py`)
- [ ] 1.6 Verify full test suite, linting, formatting, and synchronize documentation (`uv run devops docs generate --sync-readme && uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
