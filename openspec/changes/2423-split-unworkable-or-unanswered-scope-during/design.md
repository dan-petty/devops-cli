# Design

## Decisions

- **The model proposes split_issues as a structured field in its response, and the orchestrator creates the issues.**: The model identifies which parts are unworkable. The orchestrator performs the side effect of issue creation. This keeps the model read-only and the orchestrator as the single writer, matching the existing pattern.
- **Reuse the existing intake path to create split-off issues.**: CONTEXT.md states intake is the single entry point for turning a candidate into an item. A candidate is never a duplicate of the issue it is split from. Reusing intake avoids a second creation path.
- **Record links as a comment on the original issue naming each new issue number.**: The issue body already holds the job record. A comment is the existing mechanism for cross-references and is visible to a person without changing the issue body structure.

## Rejected alternatives

- **Send the whole issue to a person (NextStep.PERSON) when any part is unworkable.**: This is the current behavior described in #2423. It delays workable subsets behind blocked parts, which is the problem the issue solves.
- **Let the model create issues directly via a tool call.**: The existing pattern keeps the model read-only and the orchestrator as the writer. A tool call from the model would add a second write path and complicate the rate-limit pacing that `devops gh` enforces.
- **Close the original issue and open a new one with only the workable scope.**: This loses the history and job record of the original issue. The issue body holds the job record per ADR 0016. Keeping the original issue and splitting off the unworkable parts preserves that record.
