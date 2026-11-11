# Design

## Decisions

The decisions are in ADR 0023 (`docs/adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md`). In short:

- **The check of one item reads project context:** the tools in use, a digest of the brain and the ADR index. Two code rules correct `covers`, `partly` and `rejected`. Area checks add a project verdict and do not replace the check of one item.
- **Two tiers.** A local tier in each process, and a shared tier in `valkey-devops` and `valkey-roadmap` behind a circuit breaker. A failed Valkey write is a later miss, never a job error.
- **Three data classes.** Caches rebuild from their source. Index entries rebuild from the block of each item. Insights rebuild from hidden blocks in the run comments of one tracker issue for each repository.
- **Two CronWorkflow rows** in the unit table of ADR 0021, in the form of the metrics row. The sweep reads two due marks. A CronWorkflow is not a unit, so the rule "Only the router and the sweep create units" stays.
- **Three decision points in `shadow`,** each with the resolver chain model and fallback, until a fit and a person turn it on.
- **The amended records keep their text,** except where a row joins a list. These lists are the unit table and the engine parts of ADR 0021, and the row list of ADR 0022 section 2. Each amended record gets a note at its top, as ADR 0003 has.

## Rejected alternatives

- **Notes only, with no row in the unit table of ADR 0021.** The acceptance criteria of #4625 ask the table to hold the two rows. A reader of the table must see each schedule.
- **A rule resolver for each point now.** ADR 0020 section 2 gives a point a rule only after the rule meets its bar on labelled data. No labelled data exists yet.
- **A spec delta for the brain.** The items of tracker #4624 are not built. A requirement now would describe behavior that the code does not have. Each item adds its own delta in the nested capability.
- **Each rejected option of the brain** is in the Considered Options section of ADR 0023, with its evidence.
