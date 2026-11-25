# Design

## Decisions
- Split by dependency: the spec model has no SDK import, the builder keeps the module-level SDK import.
- The test names the blocked package in its own input. A test of this repository reads no config.

## Rejected alternatives
- Move `grafana-foundation-sdk` to the runtime dependencies: #5184 keeps it out, as it runs only in `make dashboards`.
- Import the SDK inside the builder functions: many functions use its types.
