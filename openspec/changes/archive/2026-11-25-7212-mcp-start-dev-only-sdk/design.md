# Design

## Decisions
- Split by dependency: the spec model has no SDK import, the builder keeps the module-level SDK import.
- The test reads the blocked names from `deptry.per_rule_ignores.DEP004`, so a new dev-only import of a product module is covered with no test change.

## Rejected alternatives
- Move `grafana-foundation-sdk` to the runtime dependencies: #5184 keeps it out, as it runs only in `make dashboards`.
- Import the SDK inside the builder functions: many functions use its types.
