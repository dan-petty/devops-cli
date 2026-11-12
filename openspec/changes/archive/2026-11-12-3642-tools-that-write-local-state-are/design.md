# Design

## Decisions
- The `no-external-request` class names external requests only. `readOnlyHint` of a tool follows the local writes of its command.
- The ratchet test holds the set of `no-external-request` commands that write local state or a file, as a frozen set of command paths. The audit function of the test takes the exposure table, the classes of the commands and that set as arguments, so a test can give it a table with one wrong flag. For each `no-external-request` row, the audit wants `read_only` to be true exactly when the command is not in the set.
- The audit checks both directions. A local writer with a read-only tool gives a write that the flag hides. A command that writes nothing with a tool that is not read-only leaves every role server for no reason, and it can hide a missing entry of the set.
- A member of the set that is not a `no-external-request` row of the table is an error too, so the set cannot keep a stale path.

## Rejected alternatives
- Keep the rule that each `no-external-request` tool is read-only. Rejected: six commands of the class write a local file (see the Feasibility of the proposal), so the rule makes the flag false for them.
- Add a second dry-run class or a write flag to `@dry_run_class` for a command that writes local state. Rejected: the decorator and every command callback then change for a defect of one table, and the dry-run class says what a dry run does, not what the command writes.
- Find a write from the source of a command. Rejected: a write can happen in a helper of another module (`_write_snapshot_file`, `_save_gateway_state`, `save_to_dir`), so a source scan cannot prove that a command writes nothing.
- Drop the check for a `no-external-request` command that writes nothing. Rejected: the check is what makes the set of local writers complete, because a new writer whose tool is marked not read-only must join the set.
