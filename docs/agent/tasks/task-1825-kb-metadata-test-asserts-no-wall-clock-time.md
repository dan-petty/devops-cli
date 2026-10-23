# Task: Two Tests Assert No Wall-Clock Time (#1825)

**Issue**: [#1825](https://github.com/dan-petty/devops-cli/issues/1825)
**Scope**: scope/ai
**Feasibility**: I read both tests at `release/v0.2.39` (b2b67df5) and the rules in `docs/TESTING.md`. `docs/TESTING.md` says that no test asserts on elapsed wall-clock time. It also says that the hermetic floor refuses every network socket and every program but git, so the floor proves that a test is offline and a stopwatch does not. I ran both rewritten tests on a 16-CPU host with a load average of 23 to 38. A mutation of the production code shows that the rewritten quit test still fails when the quit waits for the stream thread. An AST scan of `tests/` found 12 other assertions on elapsed time, and none is changed.

## Description

Two tests in the gate asserted a wall-clock bound. A busy machine failed both, and the code was correct each time. The change removes both bounds and keeps what each test proves.

**The knowledge base metadata test.** `test_offline_speed_under_one_second` in `tests/test_kb_manuals_metadata.py` measured three calls with `time.perf_counter()`. It failed at 1.00 s, 1.03 s and 1.49 s in pre-push gates under load. The bound counted the wait for a CPU and not the work. Alone, under a load average of 26, the test body took 0.26 s. The change deletes `start`, `elapsed`, the `assert elapsed < 1.0` line, the `time` import and "in <1s" from the docstring.

Every other assertion of the test stays. The name said "speed" and "one second", so it is now `test_floor_only_environment_matches_and_drifts_manuals_and_filtering_keeps_some`.

**The quit test.** `test_quitting_does_not_wait_on_a_silent_log_stream` in `tests/test_ui_reactive.py` read `time.monotonic()` around the quit and asserted `elapsed < 5.0`. It failed with `quitting took 5.6s while a stream was open` in the gate of the branch for #1883, under a load average of about 25. Alone, the test took 1.7 to 3 s. The silent stream waits 30 s on an event, so a bound of 5 s did not tell a hang from a slow host.

The stream now waits on `release` for twice `THREAD_HANDOFF_BOUND_SECONDS` and sets `hold_ran_out` when it gives up. After the `async with` block ends, the test asserts that `release` and `hold_ran_out` are both unset. A quit that waits for the stream ends only when the hold runs out, so the test then fails. The wait for the stream to start now uses `THREAD_HANDOFF_BOUND_SECONDS` in place of 10 s. The test and its docstring hold no clock read and no bound of 5 s. The name stays, because it is still true.

**How the quit test was shown to fail.** I added two lines to `LogPane.on_unmount` in `src/devops_cli/ui/widgets.py`, after `self.stop_stream()`. The lines are `if self._producer is not None:` and `self._producer.join()`. The quit then waits for the stream thread. The rewritten test failed with `assert (False, True) == (False, False)` after 60.65 s of call time, which is the hold running out.

I restored the file with `git checkout -- src/devops_cli/ui/widgets.py`. `git status` then showed only test files. With the production code restored, the test passes in about 1.4 s. A first mutation put the same `join` at the end of the `_consume` thread worker. The test passed with it, because Textual cancels a thread worker at shutdown and does not wait for its thread.

No new code is built, so the rule "Open Tools Before Internal Code" does not apply. The fail-to-pass check does not apply: the change removes wall-clock assertions, and the production code is correct, so both tests pass on the base and on the change.

## Acceptance Criteria

- [x] The knowledge base metadata test has no clock read and no assertion on elapsed time, and every other assertion of it stays.
- [x] The name of the knowledge base metadata test does not say "speed" or "one second". Nothing else in the repository names the old test.
- [x] The quit test has no clock read, no bound of 5 s and no "5" as a bound in its docstring.
- [x] The quit test fails when the production code waits for the stream thread on quit, shown by the mutation above.
- [x] `uv run devops ci test tests/test_kb_manuals_metadata.py tests/test_ui_reactive.py` passes.
- Fail-to-pass: not applicable. The change removes wall-clock assertions, and the production code is correct.

## Deliverables

- [x] `tests/test_kb_manuals_metadata.py`: the wall-clock assertion, `import time` and the speed wording are gone.
- [x] `tests/test_ui_reactive.py`: the quit test records its hold, asserts after the shutdown and reads no clock.
- [x] `docs/agent/tasks/task-1825-kb-metadata-test-asserts-no-wall-clock-time.md`.
- [x] `changelog.d/1825.md`.
- Not done: `tests/test_url_credential_masking.py:388` asserts `elapsed < 1.0` for each of four 100 KB inputs (`test_free_text_masking_speed`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_rag_investigator.py:218` asserts `elapsed < 1.0` for 20 concurrent lookups (`test_concurrent_lookups_wait_for_probe_outcome`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_pydantic_ai_exceptions.py:152` asserts `elapsed < 0.5` for a tool with a timeout of 0.05 s (`test_runner_tool_timeout_enforced_without_blocking`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_ui_reactive.py:1460` asserts `elapsed < 1.0` for the refresh key press (`test_a_refresh_keypress_never_blocks_on_the_providers`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_treesitter_engine.py:258` asserts `elapsed_ms < 1000.0` for one parse (`test_query_resolution_latency`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_context_packer.py:296` asserts `duration < 2.0` for one tree prune (`test_prune_tree_binary_search_under_10ms`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_fastmcp_in_process.py:130` asserts `elapsed_ms < 10000.0` for one in-process dispatch (`test_in_process_dispatcher_typer_dispatch`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_devcontainer.py:1927` asserts `time.monotonic() - start < 3` for a password prompt with a timeout of 1 s (`test_the_password_prompt_gives_up_after_its_timeout`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_github_session.py:513` asserts `time.monotonic() - started < 5.0` for a session close (`test_closing_a_session_cancels_a_request_waiting_out_a_retry`). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902).
- Not done: `tests/test_ai_review_pool.py:44` and `tests/test_ai_review_pool.py:102` assert a lower bound (`elapsed >= 0.03` and `elapsed >= 0.12`). Load only lengthens `elapsed`, so these two do not fail under load. Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902), which keeps them, because a lower bound holds on a loaded machine.
- Not done: `tests/core/test_clock_contract.py:48` asserts that the fake clock advanced by at least the wait (a lower bound with a tolerance, which load does not break). Follow-up: [#1902](https://github.com/dan-petty/devops-cli/issues/1902), which keeps them, because a lower bound holds on a loaded machine.
