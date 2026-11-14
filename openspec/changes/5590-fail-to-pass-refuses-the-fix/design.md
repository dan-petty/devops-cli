# Design

## Decisions

- **Compare the base and head outcomes of the unchanged failures instead of reading the Tests & Coverage run of main.**: The check reads no GitHub state today: `src/devops_cli/ci/fail_to_pass.py:def run_fail_to_pass` starts only git and pytest. A GitHub read would need a client, a run lookup and a mapping from a test to a run artifact.
- **Replay only the changed test files that hold an unchanged failure, and only when the base run holds one.**: A change with no unchanged failure starts no second pytest run, so the common replay keeps its cost.
- **Run the head replay and the head gate rows in one head tree, through the new `_head_tree`.**: One rule for the head tree, one worktree to add and remove, and `HEAD` keeps the working tree so an uncommitted change counts, as `src/devops_cli/ci/fail_to_pass.py:676:if head == "HEAD":` already does for the gate rows.
- **Count only a changed test as a base failure that satisfies the gate.**: The base requirement `The replay reads no title, label or body` says the command SHALL fail unless at least one changed test fails on base. Without the count, a repaired unchanged test alone would satisfy the gate.
- **Name each repaired test in the report.**: The author must tell a repaired test from a test that passed on base, and see why an unchanged failure no longer refuses the replay.
- **Keep the command help, `docs/CLI_REFERENCE.md` and `docs/commands/ci.md` unchanged.**: The help text of `devops ci fail-to-pass` states no unchanged-test rule, so no generated document contradicts the new behavior and no generator run is needed.

## Rejected alternatives

- **Read the Tests & Coverage run of main at the base commit and report the test as red on main.**: It adds a GitHub client and a mapping from a test to a run artifact to a command that starts only git and pytest, and the base spec says the replay reads no title, label or body. The two trees already hold the outcome of each test.
- **Always add a detached worktree for the head replay.**: It misses an uncommitted change of the working tree and copies the checkout for the default head; `src/devops_cli/ci/fail_to_pass.py:676:if head == "HEAD":` runs the head gate row in the working tree for that reason.
- **Let a repaired unchanged test satisfy the gate alone.**: The base requirement `The replay reads no title, label or body` says the command SHALL fail unless at least one changed test fails in the call phase on base, or a gate case fails on base and passes on head. A repair alone would prove nothing about the change.
