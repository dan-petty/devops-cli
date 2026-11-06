# Proposal

## Why

Issue #3764 is child E of #1330. Two test files of `ai/` still double a `devops_cli` name or import a private one, and one test sits in the wrong directory.

- `tests/ai/harness/test_harness_slots.py` patches `devops_cli.ai.harness.slots.load_settings` once. It imports the private helpers `_evaluate_tiered_status` and `_summarize_search` in one test.
- `tests/ai/agents/test_agent.py` holds `test_ollama_stream_400_raises_client_error`. That test checks the Ollama client, not an agent. It patches the private method `_ollama_stream_request` of an `LLMClient` instance, calls the private `_ollama_stream`, and builds its HTTP error with `MagicMock`.

## What Changes

- The status test of `devops ai harness status` sets the provider and model with the `config` fixture. It no longer patches `load_settings`.
- The test `test_tiered_synthesis_partial_status` is deleted. It built two `SubAgentResult` objects by hand and called two private helpers. No public input makes exactly one of the two searches of `AgentHarness.execute_tiered` fail (see Feasibility). A new test, `test_tiered_synthesis_reports_every_failed_search`, runs two searches on a missing directory through `execute_tiered`. It checks the failed status, the counts and the summary text, which lists both errors.
- `test_ollama_stream_400_raises_client_error` moves from `tests/ai/agents/test_agent.py` to `tests/ai/client/test_ai_streaming.py`, under the same name. It sends an HTTP 400 answer from the `web` fake and calls the public method `chat_messages_stream` with thinking on. It checks the error type, the status 400, the body text, and that the client sent one request.
- No command, option, message or request changes. The change has no spec delta, and `skip_specs: true` is set.
- The change fits one pull request.

## Impact

- `tests/ai/harness/test_harness_slots.py`, `tests/ai/agents/test_agent.py`, `tests/ai/client/test_ai_streaming.py`.
- Counts in the two named files: internal patches of a `devops_cli` name go from 2 (one in each file) to 0. Private imports go from 2 to 0.
- Out of scope: the other tests of `test_agent.py` (they test `PydanticAgent`, which #2489 deletes), file names and splits (child F), and the unreachable `partial` branch of `slots.py` (see Workflow follow-up in `tasks.md`).

## Feasibility

Checked on `origin/main` 235a807c, 2026-11-06. The text of #3764 was written at 29309f04, so each claim was read again.

- The patch at the status test, the two private imports and the misplaced Ollama test are all still in the tree. `git grep -nE 'patch\("devops_cli\.|patch\.object' -- tests/ai/harness/test_harness_slots.py tests/ai/agents/test_agent.py` found the two patches before the change and finds none after it.
- `AgentHarness.from_config` calls `load_settings()` when it gets no `AIConfig`. `devops ai harness status` reaches it that way. The `config` fixture writes `ai.provider` and `ai.model` to the per-test config file and resets the settings cache, so the command shows the written values (`uv run pytest tests/ai/harness`).
- The premise "use one repository on which exactly one of the two searches fails" is false. I ran `execute_tiered(symbol_query="foo", file_pattern="*.py")` on a directory that held a file with no read permission, a directory named `d.py`, a broken symbolic link named `broken.py`, a symbolic link loop, a directory with no access, and a file with bytes that are not UTF-8. Both searches returned `success`, and the status was `completed`. The reasons, from the source: both searches test `root.is_dir()` with the same root, so one path gives both the same answer. `parse_file_symbols` catches every read and parse error and returns `None`. `is_ignored_by_git` fails open. `pathlib.Path.rglob` skips a directory it cannot read. So the `partial` status, and the text "Some searches failed; found ..." that goes with it, have no caller with a public input. AGENTS.md rule 2 and issue #3764 (Q22) say to delete such a case and to write no code around it.
- The Ollama test works with the `web` fake because `LLMClient` builds its HTTP client through the entry point (`http_client`). `serve_llm` answers the request, and the client raises `AIClientError("Ollama returned HTTP 400. Response: ...")` with `status=400` (`src/devops_cli/ai/client/ollama.py`, `_try_single_ollama_stream`). When I changed that message in the source, the moved test failed, so the test guards the behavior. I reverted the edit.

## Existing Tool Considered

No new tool and no new code. The change uses the `config` fixture, the `web` fake with `serve_llm`, and pytest. All are open and maintained or already in the repository. `httpx2.MockTransport`, which #3764 names, would work too, but the `web` fake wraps it and the other tests of `tests/ai/client/` use the fake. The change deletes one test (`test_tiered_synthesis_partial_status`) and no source code.
