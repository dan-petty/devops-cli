# Design

## Context

Priorities for issues and backlog items must be tracked reliably on GitHub.
ADR 0001 establishes GitHub Projects as the source of truth for issue status and priority.
Currently, duplicate representations in labels and board fields cause state drift.
In addition, `devops gh issues triage` and `status` read from label taxonomy and artificially limit query results to 100 items.

## Goals / Non-Goals

**Goals:**
- Make the board's Priority field the sole authority for issue priority.
- Query every open issue through `RoadmapStore` without artificial limits.
- Update `audit_issues_triage` to flag open board items that lack a Priority value.
- Update `get_issues_summary` to group open items by their board Priority.
- Remove priority label planning from custom field reconciliation.
- Remove `type/epic` and `priority/*` from `.github/labels.yml`.
- Purge deprecated priority label strings from all active code, documentation, and tests.

**Non-Goals:**
- Automatically delete existing labels from remote GitHub repositories during CLI runs (this is performed manually by maintainers after merge).
- Add new CLI flags or commands for one-off label migration.

## Decisions

### Decision 1: Query open issues and board Priority through RoadmapStore

- **Choice**: `audit_issues_triage` and `get_issues_summary` query open items via `store.items()` and `store.candidates()`.
- **Rationale**: `store.items()` provides complete access to board fields including `priority`. `store.candidates()` retrieves open issues that are not yet on the board. Together, they cover all open issues without artificial query limits.
- **Alternatives Considered**:
  - Fetch issues via `get_repository_issues` and make individual GraphQL calls for board fields. Rejected: inefficient, hits rate limits, and bypasses the `RoadmapStore` architectural boundary.

### Decision 2: Remove Priority reconciliation completely

- **Choice**: Remove `_PRIORITY_LABELS` and `declared_priority`. `plan_item_changes` only plans `Status`.
- **Rationale**: Priority is managed on the board directly by team members and intake jobs. Reconcile should not write to Priority.
- **Alternatives Considered**:
  - Keep label-to-field synchronization as an optional flag. Rejected: violates zero zombie code rule in pre-1.0 software.

### Decision 3: Fall back gracefully when no roadmap board exists

- **Choice**: When `.github/roadmap.toml` is absent, `audit_issues_triage` and `get_issues_summary` fall back to `get_repository_issues` without query limits, reporting zero board priorities.
- **Rationale**: Allows the CLI to function on general repositories that do not configure a roadmap board.

## Risks / Trade-offs

[Risk] Existing repositories with more than 100 open issues might see changed triage and status counts.
→ [Mitigation] This is intended behavior. The previous 100-issue cap caused triage blindness.
