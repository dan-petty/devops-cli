### What happened

Some tests wait in real time, so they take longer than their work and depend on the load of the host. docs/TESTING.md says that waiting goes through the sleep and clock parameters that the libraries take, and that no test bounds or spends wall-clock time it does not need. The test-suite audit of 2026-10-24 at df8e2ee5 found three sources:

- **The Qdrant retry.** `_record_retry` ends with `time.sleep(0.5 * attempt)`. `tests/test_rag_multi_project_indexer.py:32` slept 3.0 s for real through it.
- **The process fake.** `ProcessAnswer.delay` makes `ProcessFake.run` and `run_async` call `time.sleep` and `asyncio.sleep` for the delay, or for the timeout when the delay is longer. A test that scripts a slow or hung command waits for it in real time.
- **Test bodies.** 19 tests call `time.sleep` and 5 call `asyncio.sleep` with a positive time, with no clock fixture:
  - `time.sleep`: `tests/test_ai_client_network.py:251`, `tests/test_ai_client_security.py:296`, `tests/test_ai_review_pool.py:106`, `tests/test_argo_gitops.py:87`, `:223`, `tests/test_devcontainer.py:1978`, `tests/test_github_session.py:443`, `tests/test_http_egress.py:435`, `:460`, `tests/test_k8s_service.py:516`, `tests/test_ollama_dynamic_leasing.py:61`, `tests/test_pydantic_agent.py:497`, `tests/test_rag_investigator.py:177`, `tests/test_rag_query_telemetry.py:279`, `tests/test_response_cache.py:147`, `tests/test_review_adjudication.py:301`, `tests/test_telemetry.py:678`, `tests/test_telemetry_collector_export.py:172`, `tests/test_watchers.py:68`;
  - `asyncio.sleep`: `tests/test_ai_review_pool.py:52`, `:119`, `tests/test_http_egress.py:435`, `tests/test_memory_profiler.py:182`, `tests/test_server_service.py:500`.

### What should happen

- The Qdrant retry waits through tenacity, which the project already uses, with the sleep that the one clock seam supplies. A test runs it on the `clock` fixture and asserts the waits it recorded.
- The process fake's `delay` advances the `clock` fixture's time and does not sleep. A delay longer than the timeout raises the timeout error at once.
- Each test body above shows its behaviour without a real wait: it waits for an event, or it runs on the `clock` fixture. A test that must keep two threads apart waits for the event that one of them signals (`tests/support/waits.py`).

### Evidence

At b170358e:
- `src/devops_cli/ai/rag/qdrant.py:157`.
- `tests/support/fakes/process.py:151`, `:154`, `:219`, `:222`.
- The test lines in the list above (`.data/agent/scratch/audit/full_list.txt`, sections 2.real-sleep, 2.real-sleep-static and 2.asyncio-sleep-static).

### Acceptance criteria

- [ ] `rg -n "time\.sleep" src/devops_cli/ai/rag/qdrant.py tests/support/fakes/process.py` prints nothing.
- [ ] No test in the list calls `time.sleep` or `asyncio.sleep` with a positive time, and each still checks its behaviour.
- [ ] The audit's real-sleep measure finds no test that sleeps 0.05 s or more in total. The pull request gives the before and after figures for the listed files.
- [ ] No test bounds elapsed time from above (the `test-elapsed-upper-bound` rule).
- [ ] `uv run devops ci` passes.

Out of scope: the PR monitor's poll (`github/pr_monitor.py:892`) belongs to #1321, which requires that no monitor test sleeps for real. #2138 owns the waits with a deadline of their own in `tests/test_ai_client_network.py`, `tests/test_github_session.py` and other files; this item owns only the sleeps listed above.


Source: https://github.com/dan-petty/devops-cli/issues/2138

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0abf552a0ab7b587abffcc5ade6c49407aca5e2d -->
## Proposed design

### Problem statement
Tests in the devops-cli suite wait in real wall-clock time using time.sleep and asyncio.sleep. Three sources cause this: the Qdrant retry logic in src/devops_cli/ai/rag/qdrant.py, the process fake's delay in tests/support/fakes/process.py, and 24 test bodies. These real waits make tests slow and load-dependent, violating the testing convention that waiting goes through the clock fixture or an event. The fix replaces each real wait with the clock fixture or an event-based wait.

### Acceptance criteria
- Criterion 1: No time.sleep call remains in the Qdrant retry or the process fake.
  Verification: Run `rg -n "time\.sleep" src/devops_cli/ai/rag/qdrant.py tests/support/fakes/process.py` and confirm it prints nothing.
- Criterion 2: No listed test calls time.sleep or asyncio.sleep with a positive time, and each still checks its behaviour.
  Verification: Run `rg -n "time\.sleep\(|asyncio\.sleep\("` on each of the 24 listed test files and confirm no positive-time call remains. Run each affected test and confirm it passes.
- Criterion 3: The audit real-sleep measure finds no test that sleeps 0.05 s or more in total.
  Verification: Run the audit's real-sleep measure on the listed files and confirm no test exceeds 0.05 s. Record the before and after figures in the pull request.
- Criterion 4: No test bounds elapsed time from above.
  Verification: Run the ast-grep rule `test-elapsed-upper-bound` via `devops ci` and confirm it passes with no findings in the listed files.
- Criterion 5: The full CI gate passes.
  Verification: Run `uv run devops ci` and confirm all checks pass.

### Key questions
- **Where is the clock fixture that records waits?**: It lives at tests/support/fakes/clock.py. The ast-grep rule message and its rule test both reference it by that path. [sources: .ast-grep/rules/test-elapsed-upper-bound.yml, .ast-grep/rule-tests/test-elapsed-upper-bound-test.yml]
- **Does the project already use tenacity for retries?**: Yes. The issue states the Qdrant retry uses tenacity, and the fix replaces the direct time.sleep with tenacity's sleep parameter supplied by the clock seam. [sources: src/devops_cli/ai/rag/qdrant.py:157]
- **What is out of scope for this item?**: The PR monitor poll at github/pr_monitor.py:892 belongs to #1321. Issue #2138 owns the waits with a deadline in tests/test_ai_client_network.py, tests/test_github_session.py and other files. This item owns only the 24 sleeps listed in the body. (proposed)
- **How should the process fake's delay work after the fix?**: A delay advances the clock fixture's time and does not sleep. A delay longer than the timeout raises the timeout error at once. (proposed)
- **How should the 24 test bodies show their behaviour without a real wait?**: Each test waits for an event it signals, or it runs on the clock fixture. A test that must keep two threads apart waits for the event via tests/support/waits.py. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Priority": "P1-High", "Status": "In Review", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "afcae223ef98cd18c5f90bc611f94810f839959470ee278f805389baf3ccb9a3", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "cf0bbfd31ea36dac75ed551f9c72f463b1b33722ddd2454458ef746961505643", "stage.branch": null, "stage.groups": null, "stage.needs_split": null, "stage.pr": null, "stage.sha": null} -->
