# Design

## Decisions

- **Parse removed names from removal verbs and backticked identifiers in proposal.md and design.md**: A removal verb (`remove`, `delete`, `deprecate`, `drop`, `retire`) governs the removed entity. Prepositional objects following `from`, `in`, or `of` are container names, not removed entities.
- **Account for references through tasks.md**: A referencing file is accounted for when `tasks.md` names that file.
- **Fail staging on unhandled test references**: Unhandled test references cause `devops roadmap stage` to exit non-zero with `RoadmapStageError` and open no draft pull request.
- **Warn on unhandled source references**: Unhandled references in `src/` generate warnings in the stage comment without failing the stage job.
- **Execute scan before opening draft pull request**: The scan runs after change files are built and before the draft pull request is opened.
- **Pass plans with no removals**: A plan that contains no removal statements passes with no findings.

## Rejected alternatives

- **Require a machine-readable removals section**: Planners can omit a custom section. Detecting standard prose verbs reads existing plans directly.
- **Fail on unhandled source references**: A valid removal often retains source references in registries and handlers that the task group updates during implementation.
- **Warn on unhandled test references**: Unhandled test references cause CI failures after implementation. Staging must block draft creation on test references.
- **Rely on planner model instructions**: A language model can miss references. Deterministic code search ensures consistent enforcement.
