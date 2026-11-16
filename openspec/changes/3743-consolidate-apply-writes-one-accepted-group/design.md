# Design

## Decisions

- **The apply reads the latest consolidate plan file through `last_plan`, the promoted `_last_plan` of `src/devops_cli/roadmap/consolidate.py`, and refuses a group id that the plan does not hold.**: The plan file is the record of what a person accepted, and a second source of groups would let the apply disagree with it.
- **The apply copies the `## Acceptance criteria` and `## Key questions` sections of each member byte for byte and calls no model.**: A model call costs tokens, can follow an instruction inside a member body and loses the exact text that the criterion asks for.
- **A second apply of the same merge group replaces the text between the two markers.**: The markers delimit the section, so a failed run is repairable and the anchor body does not grow.
- **The blocked-by write is the store method `add_blocked_by(blocked, blocker)` on the protocol, the GitHub store and the memory store.**: Every write stays behind the store, the `devops gh` pacing and the job-record lock, and the tests get a memory store that records the call.
- **A parent group adds a blocked-by link from each child to the anchor when the anchor holds a milestone and the children are in the backlog, and adds a sub-issue link otherwise.**: The plan records no link kind and allows only the child action for that shape, and a milestone item lands before a backlog item, so the anchor that a person planned into a milestone lands first.
- **A `close-as-duplicate` group closes the member with `close` and `CloseReason.DUPLICATE` only when the anchor is closed as completed, and writes nothing while the anchor is open.**: The plan holds that member action in `pending_closes` while the anchor is open, so the closure waits for the anchor to land.
- **The merge writer compares the anchor's Priority label with its job record and writes the highest member Priority only when the record holds the value the issue holds.**: ADR 0002 says a job compares a field with the value it last set and leaves a person's change alone, and the store has no method to set a milestone.
- **The apply resolves every target from the group and the plan's member list, and interprets no plan text.**: The write set is then a function of the plan's numbers, so a `set P0` sentence in a body or a theme cannot widen it.
- **The MCP tool `roadmap_consolidate` keeps its four parameters and publishes no `--apply`.**: `tests/ai/mcp/test_mcp_roadmap_tools.py:def test_roadmap_consolidate_is_a_read_only_mirror_of_the_plan_run` pins it as a read-only mirror, and a write option there would break that test.
- **The callers of `add_sub_issue` outside the store stay unchanged.**: `src/devops_cli/roadmap/intake/intake.py` and `src/devops_cli/roadmap/request_plan.py` call the method whose signature stays, and the change adds a method beside it.

## Rejected alternatives

- **Call the blocked-by endpoint from the command module.**: It bypasses the store contract, the `devops gh` pacing and the memory store that the tests need; every intake and refine write goes through `src/devops_cli/roadmap/stores/store.py`.
- **Close a duplicate member as not planned with the comment `Duplicate of #<anchor>`.**: `src/devops_cli/roadmap/stores/store.py:class CloseReason` holds `DUPLICATE`, and the archived REST note in `openspec/changes/archive/2026-10-29-1658-issues-close-reason/proposal.md` lists `duplicate` among the accepted values of `state_reason`.
- **Ask a model to summarize each member into the merge section.**: The criterion asks for the member sections verbatim, and a model call can follow an instruction in a member body.
- **Append a second section on a second apply.**: The anchor body would grow without bound and repeat the same criteria, so the two markers would have no use.
- **Always add sub-issue links for a parent group.**: A sub-issue link records no order, so it cannot show that a child waits on an anchor that lands first.
- **Let the scheduled run close a member of a `close-as-duplicate` group.**: No row of the Service run starts the consolidate command, and the apply runs only as a person's login with `--confirm`.
- **Use the GraphQL `duplicateIssueId` mutation for the duplicate close.**: The store sends REST only, `search_code` for `duplicateIssueId` finds no call in `src/`, and the issue rules the mutation out.

## Unchanged references

- `src/devops_cli/roadmap/intake/intake.py` (caller): It calls `add_sub_issue` only, whose signature stays, and the change adds a method beside it.
- `src/devops_cli/roadmap/request_plan.py` (caller): It builds the requests of the dry run for `add_sub_issue` only, and the apply makes no dry run of its own.
- `tests/roadmap/intake/test_roadmap_intake_sub_issues.py` (test): It tests the intake sub-issue link, which this change does not touch.
