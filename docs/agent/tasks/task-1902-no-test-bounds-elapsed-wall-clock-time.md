# Task: No Test Bounds Elapsed Wall-Clock Time, and an ast-grep Rule Holds the Tests to It (#1902)

**Issue**: [#1902](https://github.com/dan-petty/devops-cli/issues/1902)
**Feasibility**: I read each site of the issue at `origin/main` (4b06d316) and the code each test drives. I wrote the rule for `ast-grep-cli==0.51.0`, which the `constructs` row of `devops ci` already runs, and tried it on a copy of `tests/` first. ast-grep parses Python with tree-sitter, and a rule can bind a local name and find the assignment that binds it. So the rule reads the code structure, not text patterns, and the change builds no scanner of its own. The rule found the 9 upper bounds of the issue on `tests/` and no other site. The scan of `src` and `tests` takes about 0.75 s, against about 0.45 s for `src` alone.

## Description

`docs/TESTING.md` said that no test asserts on elapsed wall-clock time, and no check held the tests to it. A loaded machine stretches the time, so an upper bound fails correct code. This change removes each upper bound and adds an ast-grep rule that fails a new one.

**The rule.** `.ast-grep/rules/test-elapsed-upper-bound.yml` holds `tests/**`. Elapsed time is a clock reading minus an earlier time. Remaining time is a time minus a clock reading. A clock reading is a call of the `time` or `datetime` module that reads the current time, or a local name bound to such a call. The rule fails an operand of an ordering comparison in an assert when the operand holds elapsed time and is bounded from above, or holds remaining time and is bounded from below. The operand can hold the time itself, inside an expression, or through a local name bound to it. The list of clock reads is the closed set of the standard library's `time` and `datetime` functions that read the current time.

**A lower bound stays.** A lower bound holds on a loaded machine, as the issue says. The rule allows `tests/test_ai_review_pool.py` (`elapsed >= 0.03`, `elapsed >= 0.12`) and the real side of `tests/core/test_clock_contract.py`, which shows that a real wait lasts at least its duration. `docs/TESTING.md` now states the rule as an upper bound, the form that fails correct code.

**Each rule names its tree.** The scan now reads `src` and `tests`. The network construct rules match literal addresses, and tests hold literal addresses as test data, so each `net-*` rule now has `files: ["src/**"]`. `CONST_AST_GREP_RULE_FILES` in `src/devops_cli/config/constants.py` names the tree of each rule. The gate check in `tests/test_architectural_invariants.py` fails a rule whose `files` differ from that table, and still fails any `ignores`. The suppression count reads `# ast-grep-ignore` in `src` and `tests`, with a ceiling of 0 in each, so no comment in a test can waive the rule.

**The sites.** Each test now shows its behaviour without a clock:

- `tests/test_url_credential_masking.py`: the test checks that the masking masks each credential in the 100 KB inputs and keeps the text with none. A scan that does not stop fails at the pytest-timeout hang bound.
- `tests/test_rag_investigator.py`: 20 concurrent lookups send at most 2 requests. A lookup that did not wait for the probe would send its own request.
- `tests/test_pydantic_ai_exceptions.py`: the tool is held until the test releases it after the call returns. The test asserts that the tool was still held when the call returned.
- `tests/test_ui_reactive.py`: each provider is held until the test releases it after the refresh handler returns. The test asserts that no fetch was done when the handler returned.
- `tests/test_treesitter_engine.py`: a second parse of an unchanged file returns the map that the first parse cached.
- `tests/test_context_packer.py` and `tests/test_fastmcp_in_process.py`: the tests keep their checks of the result and read no clock. The hermetic floor refuses `devops` as a process, so the dispatch output shows that the command ran in the test process.
- `tests/test_devcontainer.py`: the prompt answers only after `THREAD_HANDOFF_BOUND_SECONDS`. A prompt that did not give up at its 1 s timeout would return the answer, and no `TimeoutError` would come.
- `tests/test_github_session.py`: the retry waits an hour. The test waits for the request with `wait_until` and joins the caller with `THREAD_HANDOFF_BOUND_SECONDS`. A close that waited out the retry would leave the caller running.
- `tests/test_process.py`: the two tests of the issue now use the spawn wrapper of #1888, moved to `_spawn_once_started`, with `STARTED_RUN_TIMEOUT_SECONDS`. The timeout fires only after the child has written its pids. `HUNG_RUN_TIMEOUT_SECONDS` had no other use and is gone.

**Sites that the issue did not list.** I found two more upper bounds, which the rule does not read because the time goes through a list:

- `tests/core/test_clock_contract.py`: the real side asserted `stamps[1] - stamps[0] < period / 2`, a bound of 15 ms. The test now records the calls and the waits of `time.sleep` in order, and asserts that no wait comes before the third call.
- `tests/test_ai_inspection.py`: `test_outline_sub_10ms_latency` asserted only an average time and the time that the product measured. `test_level_0_topology_outline` and the token tests cover the outline, so the test is gone.

## Evidence

- The new scan test failed on the base rules. With the rules of `origin/main`, a scan of a new test file with `elapsed < 1.0` found nothing (exit code 0). A scan of `local = host == "127.0.0.1"` in `tests/` reported `net-ip-literal`.
- With the change, a probe file `tests/test_zz_violation_probe.py` with `assert elapsed < 1.0` failed `ast-grep scan --error=unused-suppression --error=no-suppress-all src tests` with `error[test-elapsed-upper-bound]`. I deleted the probe after the run.
- On the sources and rules of the base, `tests/test_net_construct_rules.py` failed 14 tests in the call phase: the scan test of the new rule, the 12 scan tests of a `net-*` rule in `tests/`, and the check of the `files` of each rule. `tests/test_architectural_invariants.py` imports `CONST_AST_GREP_RULE_FILES`, which the base does not have, so a replay reports it as errored.
- `ast-grep test --skip-snapshot-tests` passed 13 rules, with 7 valid and 13 invalid cases for the new rule.
- `uv run devops ci test` over the 14 changed test modules passed 648 tests.

## Acceptance Criteria

- [x] No listed site asserts an upper bound on elapsed wall-clock time, and each test shows its behaviour without a clock.
- [x] `tests/test_process.py:433` and `tests/test_process.py:459` start their timeout after the child exists.
- [x] An ast-grep rule, run by the `constructs` row of `devops ci` and the `ast-grep-scan` commit hook, fails a new upper bound on elapsed wall-clock time in `tests/`.
- [x] A test shows that the rule fails a new violation (`test_ast_grep_scan_reports_a_new_violation_in_the_tree_its_rule_holds[test-elapsed-upper-bound]`).
- [x] `docs/TESTING.md` names the rule and its scope.
- `tests/test_host_sandbox.py:266` asserts `res.duration_seconds < 1.0`, a time that the product measures, to tell the kill at the output cap from the reap after its 1 s grace. The rule does not read it. A clockless form needs the sandbox result to tell the two kills apart. A person files the follow-up issue.

## Deliverables

- [x] `.ast-grep/rules/test-elapsed-upper-bound.yml` and `.ast-grep/rule-tests/test-elapsed-upper-bound-test.yml`.
- [x] `.ast-grep/rules/net-*.yml`: `files: ["src/**"]` on each of the 12 rules.
- [x] `src/devops_cli/config/constants.py`: `CONST_TEST_CONSTRUCT_RULES`, `CONST_AST_GREP_SCAN_ROOTS`, `CONST_AST_GREP_RULE_FILES`, `CONST_AST_GREP_RULE_ID_SEPARATOR`, and the scan of `src` and `tests`. `CONST_AST_GREP_NET_RULE_ID_RE` is gone.
- [x] `src/devops_cli/config/defaults.py`: `DEFAULT_AST_GREP_SUPPRESSION_CEILING` for `src` and `tests`.
- [x] `src/devops_cli/lang/en/messages.py` and `.pre-commit-config.yaml`: the scan of `src` and `tests`, and the new titles.
- [x] `tests/test_net_construct_rules.py`: one scan test for each rule in its own tree and in the other tree.
- [x] `tests/test_architectural_invariants.py`: the gate check for every rule, its `files` and both trees, and the suppression count in `tests`.
- [x] The test files of the sites above.
- [x] `docs/TESTING.md`.
- [x] The task files of #849, #1109, #1825 and #1888, which named the old names or a follow-up that #1902 delivers.
- [x] `docs/agent/tasks/task-1902-no-test-bounds-elapsed-wall-clock-time.md`.
