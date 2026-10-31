# Design: Dry Run Request Plans for Review Commands

## Overview

Review commands either execute local file inspections or dispatch requests to external models, gateways, Valkey, and remote repositories.
This design assigns the appropriate dry-run class to every review command and builds accurate request plans.

## Architecture

1. **Request Plans**:
   - `review benchmark`: Lists planned LLM model query and benchmark evaluation requests.
   - `review branch`, `review path`, `review pr`: Return ordered PlannedRequest items for review model calls and PR interactions.
   - `review corpus generate`, `review corpus score`: List embedding and model scoring requests.
   - `review samples fetch`: Lists git fetch and clone operations for sample repositories.
   - `review samples validate`: Lists planned model verification requests across samples.
   - `review score`: Lists planned Valkey session and metric queries.
   - `review templates check`, `review templates sweep`: List planned template evaluation and Valkey queries.
   - `review intake`: Emits planned roadmap intake requests.

2. **No-External-Request Local Commands**:
   - `review`: Main group entry point runs locally.
   - `review export-feedback`: Under dry run, prints planned export file paths and writes nothing.
   - `review findings`, `review stats`, `review templates list`, `review samples list`, `review verify`: Execute purely local queries and file operations.
   - `review rules test`: Runs local semgrep rule tests without external calls.

3. **Untrusted Trees Protection**:
   - The dry-run execution path preserves the `reading_untrusted_trees()` context manager on the review app callback.

## Alternatives Considered and Rejected

1. **Keep Simulated Review Execution under Dry Run**:
   - *Rejected*: Running mock static analyzers and saving fake sessions under dry run violates the owner's rule (#412), which dictates that dry run returns the requests that the real run would make and performs zero writes.
2. **Backward Compatibility Shim for `--dry-run` on Mark-Only Commands**:
   - *Rejected*: devops-cli is pre-1.0 software with no backward compatibility requirements. Echo-only previews are removed directly without shims.
