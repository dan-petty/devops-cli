# Task 703: Board-Owned Project Status, Declared Field Sources and Truthful Project Sync

**Issue**: [#703](https://github.com/dan-petty/devops-cli/issues/703)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/github`, `priority/p0-critical`

---

## 1. Description & Objectives

Docs say `devops gh project sync` pushes task-file status to the board (`src/devops_cli/lang/en/help.py:746-748`, `docs/MCP_TOOLS.md:852`, `docs/agent/tasks/README.md:13`), but `sync_remote_project` only counts task items (`src/devops_cli/github/projects.py:1485`). `project reconcile` recomputes Status, Priority, Category, Value and Effort every pass (`projects.py:1169-1225`), and `_filter_differing_fields` (`:1154`) overwrites differing board values, so hand corrections revert, breaking `AGENTS.md:61`. Status matches labels by substring with a Ready fallback (`:1004-1021`): `status/ready-to-merge` and `status/triage` both yield Ready, and no `.github/labels.yml` label yields Backlog. Category/Value/Effort come from `TAXONOMY_CATEGORY_MAPPING` (`:1046`) keyed on the `type/feature` label roadmap sync puts on every issue (`github/roadmap_sync.py:121`), not the ROADMAP matrix; `_derive_scope` (`:77`) keyword-matches, which `AGENTS.md:21` prohibits. Nothing records which branch decided, results are counts (`projects.py:1431-1432`), and a failed issue fetch returns `[]` (`github/issues.py:118-140`). vibes `tools/sdlc_project_manager.py` hit the same faults; `tools/portfolio_balance.py` `classify()` returns `(kind, source)`.

#### Key Deliverables:
- **Deliverable**: Measure first: `project reconcile --dry-run` lists each change with field, old and new value, and source, and `reconcile_project_custom_fields` returns that list (live runs need `read:project`). Then the board owns Status: reconcile writes it only when unset or when issue/PR state forces Done, In Review or In Progress; other moves belong to the built-in workflows `project workflows list` audits. Status labels match exactly; `status/blocked` maps only if the template gains Blocked; `CONST_PROJECT_WORKFLOW_EXPECTATIONS` expects the template's Backlog, not Todo. Reconcile never overwrites a non-empty Category/Value/Effort with an inferred value. Once a join key exists (a test that every scheduled matrix row joins its item, or a key column), sync stamps Value/Effort from the matrix and Category through a declared category map; until then it stays unset. Sync reports the `scope/cli` fallback share. Fetch failures raise, fetches paginate past 200, and reconcile refuses a missing template board instead of defaulting to board 2 (`src/devops_cli/commands/gh.py:613`). Rewrite the three `project sync` texts. Separate: suffix priority (R1-16's first PR), priority refresh in `issues reconcile-roadmap`, promotion (planned `devops gh pm deps`), Ready ordering (Sprint Kanban `sort_by`), the literal-subset lint (Anti-Brittle Constant Elimination).
- **Constraint**: Making task files write Status creates a second owner fighting the board and `Closes #N`. A reconciler that overwrites Status reverts manual triage; one that skips closed or PR-backed items leaves merged work outside Done. An inferred field that keeps writing is worse than an unset one: the board presents it as decided. A raised fetch error must stay distinct from a successful empty list, or a new repository never syncs.
- **Measured**: `gh issue list --state all --limit 2000 --json number --jq length`: 265 issues, past the 200 fetched at `roadmap_sync.py:410`. `uv run python probe/dedupe.py`: 63 of 105 open roadmap items are untracked whether the issue list is empty, capped or full, so a silent `[]` goes unnoticed. `uv run python probe/matrix_vs_reconcile.py`: inferred Effort contradicts the matrix on 71 of 93 scheduled rows. `uv run python probe/value_matrix_join.py`: 50 of 93 rows join a body item by exact title. Scratch probes, run from the devops-cli root.
- **Source**: vibes `patterns/autonomous-sdlc-project-management.md`, `tools/sdlc_project_manager.py`, `observations/devops-cli/06-rate-limits-and-anti-brittle-heuristics.md`, `tools/portfolio_balance.py`, `tools/project_tooling.py`
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

## 2. Delivered

- [x] `reconcile_project_custom_fields` returns `changes`: each field change with its item, old and new value, and the source that decided it (the planned changes in a dry run, the applied ones otherwise). `devops gh project reconcile` prints them as a table.
- [x] The board owns Status. `plan_item_changes` sets it only when unset (from an exact `status/*` label, otherwise Backlog) or when the item's state forces Done (closed issue, merged or closed pull request), In Review (open pull request, or an issue with a linked open pull request) or In Progress (draft pull request).
- [x] Status labels match exactly, so `status/ready-to-merge` and `status/triage` no longer read as Ready; `status/blocked` maps only when the board's template has a Blocked status. `CONST_PROJECT_WORKFLOW_EXPECTATIONS` expects Backlog, not Todo.
- [x] Priority only fills an unset field from its `priority/*` label. Category, Value and Effort are never inferred: no join key between the matrix and items exists, so they stay unset unless set by hand. The taxonomy and title-keyword mappings are removed.
- [x] Fetch failures raise `GitHubOperationError` instead of returning `[]` or `None`: the board items, repository issues and pull requests, and `get_repository_issues`, whose REST fallback now paginates. Roadmap sync, milestone reconciliation and release epics read every issue (`limit=None`) and no longer treat a failed read as an empty repository.
- [x] The issues fetch drops pull requests, which the pulls fetch supplies with their merge state, so each pull request is reconciled once.
- [x] `project reconcile` and `project workflows list` refuse to guess board #2 when no board matches the template.
- [x] `devops gh issues sync-roadmap` reports how many eligible items fell back to `scope/cli`.
- [x] The `project sync` help, the `gh_project_sync` and `gh_project_reconcile` MCP descriptions, `docs/agent/tasks/README.md` and the project-management knowledge base say what sync and reconcile do.

## 3. Verification

- `devops gh project reconcile --dry-run` against board #2 (read-only): would change 337 of 472 items, 480 field changes. Every change fills an unset field or forces a closed item to Done: Status unset to Done 212, unset to Backlog 81, unset to In Review 2, set to Done (closed) 42; Priority unset to a label's value 143. No set Status is moved for any other reason, and no Category, Value or Effort is written. Before dropping pull requests from the issues fetch, the same run counted 683 items, reconciling each pull request twice.
- The 15 test files that touch projects, issues, roadmap sync, release epics and the `gh` commands: 351 passed.
