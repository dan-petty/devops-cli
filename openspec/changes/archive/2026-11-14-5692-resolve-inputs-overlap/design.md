# Design

## Context

Issue #5692 resolves the requirement rewrite overlap between active changes #3148 and #5451 on capability `roadmap-implement-step/inputs`.

## Decisions

- Change 3148 introduces read-only requirements for code intelligence tools (`ai ast` and `ai repomap`).
- Converting this requirement from `MODIFIED` to `ADDED` under the name "The code-intelligence commands of the catalog are read-only" isolates it from 5451's modification and rename of "The prompt lists the local devops commands of the catalog".
