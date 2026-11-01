# Design

## Decisions

- **Build each PlannedRequest from the same argument builder the real run uses**: The issue states the plan cannot drift from the run. Using the same builder guarantees the plan matches the real requests.
- **Remove echo-only previews with no shim**: The issue says 'with no shim' and the pre-1.0 policy in the repository deletes rather than keeps behind flags.
- **Group commands by family and work type (mark-only vs request-plan)**: Each group fits the 40000-token budget. A group of 2-5 commands in one file keeps the step small and focused.
- **Use the existing PlannedRequest and render_request_plan**: They exist in the repository (#741) and are the established pattern. Building new rendering would duplicate code.

## Rejected alternatives

- **Build a new dry-run rendering module for these commands**: render_request_plan and PlannedRequest already exist (#741, #885 in CHANGELOG.md). Building a new one duplicates code and diverges from the established pattern.
- **Keep echo-only previews as a fallback behind a flag**: The issue says 'with no shim'. The pre-1.0 policy in the repository (ADR 0005, CONTEXT.md) deletes rather than keeps behind flags.
- **Add a new dependency for dry-run planning**: The issue states 'No new dependency is necessary.' The repository already has the full dry-run infrastructure.
