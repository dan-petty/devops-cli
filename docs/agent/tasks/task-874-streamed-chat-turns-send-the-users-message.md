# Task: Streamed Chat Turns Send User Message and Roll Back on Failure (#874)

**Issue**: [#874](https://github.com/dan-petty/devops-cli/issues/874)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-important
**Scope**: scope/ai

## Description

Prior to this fix, `_stream_interactive_chat_turn` built `messages = agent.memory.to_chat_messages()` without adding the active user turn (`effective_prompt`) to `agent.memory`. Consequently:
1. The first streamed turn sent an empty messages array (`[]`) to the model provider instead of the user prompt, causing blank or contextless responses.
2. In subsequent turns, the user's prompt was only recorded in `agent.memory` when the assistant response completed, meaning prior turns were present in memory but the current turn prompt was omitted from `messages`.
3. In `devops ai chat`, `except Exception` popped `agent.memory.entries[-1]` unconditionally without verifying the entry's role, and `except KeyboardInterrupt` did not roll back memory, potentially leaving corrupted or inconsistent memory state.
4. If a streamed response produced thinking-only output, falling back to `agent.run(effective_prompt)` without rolling back the user entry could duplicate the user prompt in memory.

This change resolves these defects:
1. `_stream_interactive_chat_turn` records `agent.memory.add_interaction("user", effective_prompt)` before calling `client.chat_messages_stream`, ensuring both prompt and conversation history are sent to the provider.
2. If the stream yields thinking-only output, trailing user entries are popped from memory before delegating to `agent.run(effective_prompt)`, ensuring the prompt is recorded exactly once.
3. In `devops ai chat`, both `except KeyboardInterrupt` and `except Exception` handlers check `if agent.memory.entries and agent.memory.entries[-1].role == "user": agent.memory.entries.pop()`, leaving conversation memory in its pre-turn state upon error or interruption.

## Acceptance Criteria

- [x] **Streamed turns send the user's message and history**: On turn 1, `messages` contains `[("user", "p1")]`. On turn 2, `messages` contains `[("user", "p1"), ("assistant", "r1"), ("user", "p2")]`, and memory records both turns.
- [x] **A failed or interrupted streamed turn leaves memory as it was before the turn**: When a streamed turn fails with `AIClientError` or is aborted with `KeyboardInterrupt`, memory is rolled back to its pre-turn state and subsequent turns proceed cleanly.
- [x] **The thinking-only fallback stores the prompt once**: Stream turns producing only thinking blocks fall back to `agent.run` and record exactly one user entry in memory.
- [x] **The #599 test matches the new contract**: `test_a_cut_stream_stores_no_reply_in_chat_memory` verifies that a cut stream under the helper alone leaves the single user entry and no assistant reply.
- [x] **No network**: All tests utilize offline fakes for `chat_messages_stream` and `chat_messages`, patched `investigate_rag_context`, and respect `prevent_external_network_calls`.
- [x] **Speed**: All new and updated tests execute under 0.25 s serially in `pytest`.
- [x] **Gate**: `uv run devops ci` completes with 100% passing quality gates.
- [x] **Fragment and task file**: `changelog.d/874.md` exists with `### Fixed`; `docs/agent/tasks/task-874-streamed-chat-turns-send-the-users-message.md` exists with `**Status**: Done`; `CHANGELOG.md` and `docs/ROADMAP.md` remain untouched.
- Pending a person: in `uv run devops ai chat --no-tools`, ask "What is 2+2?". The reply answers that question. Then ask "And times 3?"; the reply uses the first answer, showing the history was sent. Then ask a third question and press Ctrl-C while the reply streams; "Interrupted." prints, and a fourth question gets a reply that still follows the earlier answers.

## Deliverables

- [x] `src/devops_cli/commands/ai.py` updated to add user turn to `agent.memory` before streaming, pop before `agent.run` thinking fallback, and conditionally roll back user entry on exception or interrupt.
- [x] `tests/test_ai_cmd.py` updated with `test_a_cut_stream_stores_no_reply_in_chat_memory` contract update, `test_a_streamed_turn_sends_the_user_message_and_history`, `test_a_failed_streamed_turn_leaves_memory_as_it_was`, and `test_a_thinking_only_stream_stores_the_prompt_once`.
- [x] `changelog.d/874.md` changelog fragment under `### Fixed`.
- [x] `docs/agent/tasks/task-874-streamed-chat-turns-send-the-users-message.md` task document.
