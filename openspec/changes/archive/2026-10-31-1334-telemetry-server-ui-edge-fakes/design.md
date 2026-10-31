# Design

## Context

Issue #1334 migrates `telemetry/`, `server/`, `ui/`, `output/`, and `docs/` tests to edge fakes, dissolves internal monkeypatches, removes private imports, moves command logic into domain packages, and decomposes monolithic test suites into behaviour-focused test files.

## Alternatives Considered

- **Splitting into multiple pull requests across subpackages**:
  - *Rejected*: Roadmap record for #1334 states `needs_split: false` and `Fits in one pull request`. Keeping the package migrations in one coherent PR prevents drift between interconnected telemetry, server, and UI test contracts.
- **Keeping test_ui_reactive.py as a single file**:
  - *Rejected*: The file spans nearly 3,000 lines and 24 distinct sections. The testing architecture requires test files to be organized by behaviour rather than large catch-all suites. Splitting into 24 behaviour-specific files improves readability and test discovery.
- **Keeping domain validation logic in commands/serve.py and commands/telemetry.py**:
  - *Rejected*: ARCHITECTURE.md and #1307 require commands to remain thin adapters handling CLI options, argument parsing, rendering, and exit codes. Moving `_validate_service_mode`, `_run_profiled_command`, and `_read_trace_from_tempo` to `server/service.py` and `telemetry/waterfall.py` establishes proper layering and testability.
- **Manual regex matching for full-table string assertions**:
  - *Rejected*: Syrupy snapshot testing (`snapshot`) provides stable, maintainable test assertions for complex multi-line text tables and documents without fragile manual string manipulation.
