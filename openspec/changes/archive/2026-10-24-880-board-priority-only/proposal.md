# Proposal

## Why

ADR 0001 establishes the GitHub Projects board as the source of truth for roadmap priorities.
Priority currently exists in both GitHub labels and the board's Priority field.
These two locations drift apart because changes in one location do not propagate to the other.
Additionally, `gh issues triage` and `gh issues status` read priority from labels instead of the board.
They also cap issue queries at 100 items, missing issues in larger backlogs.
Reconcile also sets priority from labels when the field is empty.
This change establishes the board's Priority field as the sole source of priority and removes redundant labels.

## What Changes

- `gh issues triage` and `gh issues status`, and their MCP mirrors, read all open issues and Priority through the roadmap store.
- Triage flags an open item that has no board Priority. Backlog items without milestones are not flagged.
- Reconcile stops reading priority labels: remove `_PRIORITY_LABELS` and `declared_priority` from `src/devops_cli/github/projects.py`.
- `.github/labels.yml` drops `type/epic` and the four `priority/*` labels.
- Documentation in `AGENTS.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, and task guides is updated to reference the board's Priority field.
- All references to `priority/(p[0-3]|high|medium|low)` are removed from source, tests, and test fixtures.
- New unit tests against `InMemoryRoadmapStore` verify triage and status priority reporting offline.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/github/issues.py`: `audit_issues_triage` and `get_issues_summary` use `RoadmapStore` to inspect all open items and their board Priority.
- `src/devops_cli/github/projects.py`: remove `_PRIORITY_LABELS` and `declared_priority`; stop reconciling Priority.
- `src/devops_cli/commands/gh.py`: update `issues_triage_cmd` and `issues_status_cmd` to pass or open the roadmap store and display board priority metrics.
- `.github/labels.yml`: remove `type/epic` and the four `priority/*` label specifications.
- `docs/ROUTINE_TASKS.md`, `AGENTS.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`: update references from priority labels to the board Priority field.
- `tests/fixtures/roadmap/*` and `tests/*`: remove obsolete priority label references.

## Feasibility

- Examined `src/devops_cli/github/projects.py` lines 788-793 and lines 832-870. Removing `_PRIORITY_LABELS` and `declared_priority` cleanly restricts reconcile to Status field planning.
- Examined `src/devops_cli/github/issues.py` lines 293-351. `audit_issues_triage` and `get_issues_summary` can query `store.items()` and `store.candidates()`.
- Verified `InMemoryRoadmapStore` in `src/devops_cli/roadmap/memory_store.py`. It provides `items()`, `candidates()`, and board field access offline.
- Checked `.github/labels.yml` lines 37-39 and lines 98-114. The labels can be deleted without affecting repository schema integrity.

## Existing Tool Considered

This change uses the existing `RoadmapStore` protocol and `InMemoryRoadmapStore` implementation from #768.
No external tool or library is required.
