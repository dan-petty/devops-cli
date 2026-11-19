## Purpose
The pinned GenAI semantic conventions snapshot of devops-cli and its refresh command `devops telemetry semconv refresh`, which resolves the conventions with weaver.

## ADDED Requirements

### Requirement: The weaver install hint names no version
When no `weaver` is on PATH, the `DependencyError` of `devops telemetry semconv refresh` SHALL name the devtools image `ghcr.io/dan-petty/devtools` and the weaver releases page. The hint SHALL hold no weaver version number, because Renovate updates the version only in the devtools image.

#### Scenario: Weaver is absent from PATH
- **WHEN** `devops telemetry semconv refresh --commit <sha>` runs and no `weaver` is on PATH
- **THEN** the command exits 1
- **AND** the message names `ghcr.io/dan-petty/devtools` and `https://github.com/open-telemetry/weaver/releases`
- **AND** the message holds no version number
