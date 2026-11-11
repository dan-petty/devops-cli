# Design

## Decisions

- **One rule, one document.** A rule goes into the document that AGENTS.md routes its topic to. The push rules of a pull request go to `docs/SDLC.md`, Phase 6. Cadence B of `docs/ROUTINE_TASKS.md` now links there, because it was a copy that had gone stale (the old catch-up rule and the board steps).
- **AGENTS.md stays under its cap.** Only rules for every task change there. The `BREAKING CHANGE:` clause moves out, because `CONTRIBUTING.md` section 4 states it, and the release paragraph is shorter. The file has 6,494 characters.
- **State the code as it is.** The trace propagation text names each path that the code has. The rag-ingest text says that the controller does not watch namespace `devops`.
- **Fix the same stale fact everywhere.** The nesting cap of the feature request template changes with the documents.

## Rejected alternatives

- **Write the 1-minute tolerance of the check limit.** AGENTS.md rule 5 says 5 minutes, and only the owner can loosen a threshold.
- **Write rules for features that are not built**, such as the project brain, the design spec or a push guard. AGENTS.md rule 8: a document states only what `main` has after the merge.
- **Hand-edit `docs/TELEMETRY.md` or an ADR.** `docs/TELEMETRY.md` is generated, and an ADR is a record.
- **Add a route row to AGENTS.md for web pages.** The file has 6 characters of room, so the route goes into the contributor guide that AGENTS.md links.
