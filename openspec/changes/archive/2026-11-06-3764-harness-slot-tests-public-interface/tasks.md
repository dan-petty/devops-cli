# Tasks

## 1. The harness slot tests use the public interface (test-only edits)

- [x] 1.1 Replace the `load_settings` patch in `test_cli_ai_harness_status_reads_the_configured_model` with the `config` fixture.
  Verification: `uv run pytest tests/ai/harness/test_harness_slots.py -k configured_model`
- [x] 1.2 Delete `test_tiered_synthesis_partial_status` with its private imports. Add `test_tiered_synthesis_reports_every_failed_search`, which uses `AgentHarness.execute_tiered`.
  Verification: `uv run pytest tests/ai/harness/test_harness_slots.py -k tiered_synthesis`
- [x] 1.3 Check that the file holds no patch and no mock, and imports no private name.
  Verification: `! git grep -n -e patch -e MagicMock -e _evaluate_tiered_status -e _summarize_search -- tests/ai/harness/test_harness_slots.py`

## 2. The Ollama client test moves to the client tests (test-only edits)

- [x] 2.1 Move `test_ollama_stream_400_raises_client_error` from `tests/ai/agents/test_agent.py` to `tests/ai/client/test_ai_streaming.py`. Answer HTTP 400 from the `web` fake and call `chat_messages_stream`.
  Verification: `uv run pytest tests/ai/client/test_ai_streaming.py -k ollama_stream_400`
- [x] 2.2 Check that the agent test file holds no test of the Ollama client and no patch of the client.
  Verification: `! git grep -n -e ollama -e mocker -e patch -- tests/ai/agents/test_agent.py`

## 3. The change leaves no stale name (documents)

- [x] 3.1 Check that no document or test names the deleted test or the old place of the moved test.
  Verification: `! git grep -n -e test_tiered_synthesis_partial_status -e test_agent.py::test_ollama -- src tests docs README.md ARCHITECTURE.md SECURITY.md`
- [x] 3.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- The `partial` status of `_evaluate_tiered_status` and the prefix "Some searches failed; found" of `_summarize_search` in `src/devops_cli/ai/harness/slots.py` have no public input that reaches them. Issue #3852 deletes them.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
