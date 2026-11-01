# Tasks

## 1. Remove the `_prepare_cmd` alias

Reads: `src/devops_cli/core/process.py` lines 470 to 482, `tests/core/test_process.py` lines 575 to 600, `tests/support/fakes/process.py` lines 18 to 26, 240 to 275 and 355 to 365. Changes: `src/devops_cli/core/process.py`, `tests/core/test_process.py`, `tests/support/fakes/process.py`.

This group keeps behavior, so it adds no test. The repeatable check is `git grep -n "_prepare_cmd" -- src tests`. It prints 8 lines on the base and nothing when the group is done.

- [ ] 1.1 Run `git grep -n "_prepare_cmd" -- src tests` and note the 8 lines. In `tests/support/fakes/process.py`, import `prepare_tool_cmd` at the top in place of `_prepare_cmd`, call it in the two places that call `_prepare_cmd(cmd)`, and make the method `prepare_cmd` use the top-level import and not a local one. Verify with `uv run devops ci test tests/core/test_process_contract.py tests/core/test_process_hardening.py`
- [ ] 1.2 In `tests/core/test_process.py`, import and call `prepare_tool_cmd` in `test_uv_preview_flags_injection`, with the same expected values. Verify with `uv run devops ci test tests/core/test_process.py`
- [ ] 1.3 Delete the line `_prepare_cmd = prepare_tool_cmd` and its blank lines from `src/devops_cli/core/process.py`. Verify that `git grep -n "_prepare_cmd" -- src tests` prints nothing and that `uv run devops ci test tests/core/test_process.py tests/core/test_process_contract.py tests/core/test_process_hardening.py tests/commands/test_ci.py` passes. The full suite, which holds the 128 files that use the process fake, runs in CI

## 2. Set the `src noqa: F401` ceiling to 0

Reads: `tests/invariants/test_architectural_invariants.py` lines 176 to 196 and 2505 to 2525. Changes: `tests/invariants/test_architectural_invariants.py`.

This group changes a test constant and no behavior, so it adds no test. The repeatable check is the probe in 2.1 to 2.4. It shows that a new unused `# noqa: F401` import in `src/` passes the ratchet at 15 and fails it at 0.

- [ ] 2.1 Confirm the count: `git grep -n "noqa: F401" -- src` prints nothing, and `uv run ruff check --select F401 --ignore-noqa src` prints `All checks passed!`
- [ ] 2.2 Probe the base. Write the line `import os  # noqa: F401` to the new file `src/devops_cli/f401_probe.py`. Run `uv run devops ci test tests/invariants/test_architectural_invariants.py -k suppressions_stay_under_their_ceilings`. It passes, which is the gap. Delete the probe file
- [ ] 2.3 In `DEFAULT_SUPPRESSION_CEILINGS`, change `"src noqa: F401": 15` to `"src noqa: F401": 0`
- [ ] 2.4 Repeat the probe of 2.2. The run now fails with `src noqa: F401: 1 > ceiling 0`. Delete the probe file, and verify with `git status --short` that no file under `src/` is changed and with `uv run devops ci test tests/invariants/test_architectural_invariants.py` that the file passes. Put the output of 2.2 and 2.4 in a comment on the pull request
