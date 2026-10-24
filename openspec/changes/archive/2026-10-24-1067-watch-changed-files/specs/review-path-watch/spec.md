# Spec Delta

## Purpose

`devops review path --watch` monitors target paths and reviews only the files that changed on each change event.

## ADDED Requirements

### Requirement: Path review watch mode reviews only changed files
When `devops review path` runs with `--watch`, each filesystem change SHALL review only the changed files that exist, lie under one of the target paths, and pass `--pattern` and reviewable-file filters. A change with no reviewable files SHALL print one line and run no review session.

#### Scenario: Watched directory contains modified reviewable file
- **WHEN** `devops review path` runs with `--watch` on a directory holding multiple files, and one file changes
- **THEN** the review workflow receives pages for only the changed file

#### Scenario: Watched change contains only non-reviewable or deleted files
- **WHEN** `devops review path` runs with `--watch` and a change event contains only deleted files or files that pass no reviewable filters
- **THEN** no review workflow runs and the command prints that no reviewable files changed
