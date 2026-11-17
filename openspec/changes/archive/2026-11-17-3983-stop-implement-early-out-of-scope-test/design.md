# Design

## Decisions

### Parse test output at step exit check
Parse the command output when a verification command fails during the step exit check.
Extract failing test node IDs starting with `FAILED `.
Map each failing test to its file path and compare that path to the group's `Changes:` list.
This uses the existing command output and requires no additional subprocess runs.

### Classify stop as false premise
Classify the stop with `FailureClass.PREMISE_FALSE`.
This causes `_extra_ask` to return `None`, preventing any extra repair turn or model requests.
The item returns to New so the plan can be updated to include the test.

### Allow Changes paths and change tasks.md
Treat the group's `Changes:` paths and the change's `tasks.md` as allowed paths.
A failure in a test file outside these paths triggers the early stop.

### Format stop evidence clearly
Format the stop message to name both the failing test node ID and its file path outside `Changes:`.

## Rejected alternatives

### Block edits at tool boundary only
Rejected: it stops the edit attempt but does not stop the step or name the failing test.

### Run a separate invariant test command
Rejected: it duplicates the verification check and increases execution time.

### Classify stop as LimitReached or Blocked
Rejected: `LimitReached` spends the full budget, and `Blocked` waits for manual retry without fixing the plan.
