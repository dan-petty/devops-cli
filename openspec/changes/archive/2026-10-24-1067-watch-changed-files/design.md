# Design

## Context

`devops review path --watch` continuously monitors target paths for changes.
The watcher detects changed paths and passes them to `_on_change(changed)`.
Previously, `_on_change` ignored the changed paths and executed a full review over all target directories.

## Goals / Non-Goals

**Goals:**

- Filter watched file changes to existing, reviewable files that reside under target paths and match patterns.
- Review only the filtered changed files in a single review session.
- Skip deleted files without raising an error.
- Print one informational line and run no review session when no reviewable files changed.
- Keep all other review settings (stage flags, personas, concurrency, clients) identical to the main target configuration.

**Non-Goals:**

- Modifying `review branch` or `review pr`, which do not provide `--watch`.
- Running an initial full review before the first change event.

## Decisions

- **Filter changed paths against targets and review criteria in `_prepare_watch_content`.**
  A helper function resolves each changed path, checks existence, confirms containment under one of `path_targets`, applies `--pattern` glob matching, checks git ignore rules, and filters secret-scan-only files.
- **Deduplicate and sort reviewable files.**
  Sorting files ensures deterministic page order for testing and reporting.
- **Print one line and skip review when no reviewable files change.**
  When `changed` contains only deleted files, ignored files, or non-matching patterns, the command prints `MESSAGES.review.no_reviewable_files_changed` and returns to watching.
- **Pass filtered pages to `_execute_current_review`.**
  `_execute_current_review` accepts an optional `pages` list. When provided, it preserves `target_dir`, `target_ref`, and review settings while substituting the specific file pages.

## Risks / Trade-offs

- [A changed file imports symbols from an unchanged file] → The unchanged file is not re-reviewed, matching single-file path review behavior. Linked file lookups and repository RAG remain available.
