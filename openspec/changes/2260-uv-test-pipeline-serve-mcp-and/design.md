# Design

## Decisions

- **Pass-through commands (uv run, pipeline) list the delegated argv, stdin, env, condition, and repeat as their plan.**: The proposed design in the issue confirms this. The plan uses the same argument builder as the real run, so it cannot drift. The CHANGELOG shows the same pattern for 15+ prior command groups.
- **Server commands (serve, mcp serve) list the bind and start requests, not client calls.**: A server makes requests only when a client calls it. The dry run lists what the server would bind and start. This matches the issue's note.
- **mcp tools gets the no-external-request class rather than a request plan.**: The issue table marks it as mark-only: it makes no external request and needs only the no-external-request class.
- **mcp export-schemas gets a local preview rather than a request plan.**: The issue table marks it as local preview: it changes local state, makes no external request, and has no --dry-run today.
- **Echo-only previews are removed with no shim.**: The issue states: Remove an echo-only preview when the command gets its new dry run, with no shim.

## Rejected alternatives

- **Keep echo-only previews alongside the new request plans.**: The issue states: Remove an echo-only preview when the command gets its new dry run, with no shim. The CHANGELOG shows prior deliveries removed echo-only previews in the same step.
- **Give pass-through commands a different design than a request plan.**: The proposed design in the issue answers: Yes. It lists the delegated argv, stdin, env, condition and repeat. It uses the same argument builder as the real run. Sources: CHANGELOG.md:1390, tests/test_roadmap_dry_runs.py.
- **Split the 14 commands into separate issues.**: The issue states: These groups each have fewer than 5 commands that need work, so they join here. The proposed design confirms: Fits in one pull request.
