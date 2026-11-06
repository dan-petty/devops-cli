# Design

## Context

See proposal.md for the scope (#3764, child E of #1330). The seams used here exist already: the `config` fixture (#1310) and the `web` fake with `serve_llm` (#3755, #3791).

## Decisions

### 1. The partial-status test is deleted, not rewritten
- **Decision**: delete `test_tiered_synthesis_partial_status`. Add `test_tiered_synthesis_reports_every_failed_search`, which drives `AgentHarness.execute_tiered` with a symbol query and a file pattern on a missing directory.
- **Why**: the old test reached the branch only by building `SubAgentResult` objects by hand. The probe in the Feasibility section found no public input that fails one search and not the other.
- **Rejected**: swap a failing sub-agent into `AgentHarness.subagent_slot` with a subclass or a patch. That doubles an internal object, which is what this change removes.
- **Rejected**: keep the private-import test. The issue forbids private imports in the file.

### 2. The moved Ollama test uses the `web` fake
- **Decision**: build a real `LLMClient` for `provider="ollama"`, answer HTTP 400 through `serve_llm`, and call `chat_messages_stream(enable_thinking=True)`.
- **Why**: the other client tests do the same, and the fake keeps the egress check and the retry transport of the real client in the path.
- **Rejected**: a hand-built `httpx2.MockTransport` passed to `LLMClient`. It works, but it bypasses the fake that all other tests of the folder share.

### 3. The moved test goes to `test_ai_streaming.py`
- **Decision**: the test sits next to the other Ollama stream test of that file.
- **Why**: it checks the stream path of the client. `test_ai_client_security.py` holds the non-stream 400 case and calls a private method.
