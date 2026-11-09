# Proposal: #3852

## Why

Issue #3852 removes unreachable dead code found while working on #3764 (child E of #1330).

The function `_evaluate_tiered_status` in `src/devops_cli/ai/harness/slots.py` returns `partial` when some sub-agent searches succeed and some fail. `_summarize_search` then writes "Some searches failed; found ...". No public input reaches this branch.

Both searches of `AgentHarness.execute_tiered` use the same `repo_path` and test `root.is_dir()` on the same root, so they fail together. The read and parse helpers catch their own errors, so a single search does not fail alone. The only test of the branch built synthetic `SubAgentResult` instances and called private helpers. Issue #3764 deleted that test.

Closes #3852.

## What Changes

- Remove the `partial` status from `_evaluate_tiered_status` in `src/devops_cli/ai/harness/slots.py`.
- Return `completed` when every search succeeds and `failed` otherwise.
- Remove the text "Some searches failed; found" from `_summarize_search`.
- Keep the `failed` status and summary when searches fail on a missing directory.

## Capabilities

None. This change removes dead internal code.

## Impact

- `src/devops_cli/ai/harness/slots.py` contains neither `partial` nor "Some searches failed".
- No command, option, setting or external interface changes.

## Feasibility

Checked on `origin/main` 84117ace.

- `git grep -n -e partial -e "Some searches failed" -- src/devops_cli/ai/harness/slots.py` shows lines 637 and 660 hold the only occurrences.
- `tests/ai/harness/test_harness_slots.py` tests both successful execution and failure isolation on missing directories.

## Existing Tool Considered

None needed. The change removes unreachable dead code.
