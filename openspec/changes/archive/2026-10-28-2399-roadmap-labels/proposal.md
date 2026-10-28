# Proposal

## Why

Issue #2399: the roadmap Service moves to a GitHub App that the personal account `dan-petty` owns (#1647). GitHub gives an App the "Projects" permission only at organization level, so the App cannot read or write board 12, which a user owns. Every roadmap job needs that board today: an Item is an issue with a card, its Status, Priority, Value and Effort are card fields, and the job record is the board's TEXT field `Job record`.

The owner decided on 2026-10-28: labels and milestones hold an Item's state, no roadmap job reads or writes the project board, and private boards need no support. The owner keeps the board as a personal view through label and milestone filters.

## What Changes

- An Item is an issue of the repository, not a pull request, that holds a `priority/*` label: intake placed it, or a person did. A Candidate is an open issue with no `priority/*` label.
- Each of Status, Priority, Value and Effort is one label family: `status/new`, `status/ready`, `status/in-progress`, `status/in-review`, `status/blocked`; `priority/p0-critical`, `priority/p1-high`, `priority/p2-medium`, `priority/p3-low`; `value/high`, `value/medium`, `value/low`; `effort/high`, `effort/medium`, `effort/low`. The field values keep the names the board options had, such as `P1-High` and `In Progress`. A closed issue is done, so no label holds Done.
- A job sets a field with one `PATCH` of the issue that replaces the labels of the family and writes the job record. The job record moves from the board's `Job record` field to a hidden block at the end of the issue body. The body that the jobs read and write has no block, and a body write keeps it.
- A job's write still refuses, before it changes anything, a field that a person changed since the store read it (ADR 0002). When a family holds two labels, the field's value is the one that the job record does not name.
- The store, `board_read.py`, `.github/roadmap.toml` and its reader, the `Job record` field check, `add_item`, the card restore, the board filters, the GraphQL budget probe of the board, the round's GraphQL spend line and the Service's pause after a board budget refusal go. The Projects reads that `devops gh project` uses move to `src/devops_cli/github/project_read.py`.
- Intake places a candidate with labels: a `type/*` label when it has none, the fields it holds no value for, the reason comment, then Priority. A run that stops part-way leaves a candidate, and the next run decides it again.
- `devops roadmap refine`, `run` and `return` lose `--ref`, which only chose the ref of `.github/roadmap.toml`. Intake keeps `--ref` for `.github/labels.yml`.
- `devops pr check-readiness` blocks a pull request whose one issue holds no `priority/*` label, in place of an issue with no card on the board. It reads the labels in the closing-issues query that it already sends.
- `devops gh project reconcile` drops its "awaiting intake" line, because intake adds no card. The project template drops the `Job record` field, and its triage view, like `.gh-dash.yml`, filters on `status/new` in place of `status/triage`.
- `devops gh issues triage` reads the Items and the Candidates from the store, which never overlap: an Item always holds a Priority, so the "Missing Priority" row goes.
- `.github/labels.yml` declares the four families. ADR 0016 amends ADR 0001, 0002 and 0003.
- The change carries spec deltas: a new capability `roadmap-item-labels`, and changes to `roadmap-refine`, `project-metrics-dashboard` and `roadmap-intake-duplicates`. The labels a job writes, the commands' options and the readiness blocker are observable.
- It fits one pull request. The store's interface changes for every caller at once, so a split would leave `main` with two stores or a shim.

## Capabilities

### New Capabilities

- `roadmap-item-labels`: how labels and the issue body hold an Item's fields and job record, and how a job writes them.

### Modified Capabilities

- `roadmap-refine`: the roadmap configuration file and its one key go.
- `project-metrics-dashboard`: the items gauge counts the Items of the repository, its priority from the label.
- `roadmap-intake-duplicates`: the scenarios name labels in place of the board.

## Impact

- Code: `src/devops_cli/roadmap/` (`store.py`, `github_store.py`, `memory_store.py`, `intake.py`, `intake_requests.py`, `request_plan.py`, `return_item.py`, `run.py`; `config.py` and `board_read.py` deleted), `src/devops_cli/github/` (`project_read.py`, `projects.py`, `owner_lookup.py`, `metrics.py`, `issues.py`), `src/devops_cli/commands/` (`roadmap.py`, `pr.py`, `gh.py`, `serve.py`), `src/devops_cli/survey/intake.py`, the constants, messages and help texts.
- Files: `.github/labels.yml`, `.github/project-template.json`, `.gh-dash.yml`, the descriptions of two panels of `k8s/monitoring/dashboards/project-metrics.json`; `.github/roadmap.toml` deleted.
- Documentation: ADR 0016, the notes on ADR 0001, 0002 and 0003, `CONTEXT.md`, `README.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, the knowledge base, and the generated command references.
- Tests: the roadmap tests, the GitHub fakes in `tests/`, and the tests of `devops gh project`, `devops pr` and `devops gh issues triage`.
- Data: the board values of the open issues of each managed repository become labels once. A scratch script prints the labels to set; a person decides when to apply it.

## Feasibility

- GitHub's "Permissions required for GitHub Apps" page lists "Organization permissions for Projects" and no repository permission for Projects. Its "Repository permissions for Issues" section gives write access to labels and milestones and to the labels of an issue.
- GitHub's REST reference for "Update an issue" (`PATCH /repos/{owner}/{repo}/issues/{issue_number}`) takes `body` and `labels` in one request, and `labels` "replace[s] the set of labels on this issue". So one request writes the field and its record together.
- `uv run devops gh api 'repos/dan-petty/devops-cli/issues?state=all'` on 2026-10-28 returns each issue's `body` and `labels` in the listing that the store already reads, so the record in the body costs no read per Item. The repository's issues hold `priority/p0-critical` 86 times, `priority/p1-high` 365, `priority/p2-medium` 259, `priority/p3-low` 65, `status/blocked` 18 and `status/in-progress` 95, so the existing labels are in use and are kept.
- The refine section of an issue body is already a hidden block between two HTML comments (`CONST_ROADMAP_REFINE_START_MARKER`), so a hidden block in the body is a form that the jobs read and write today.

## Existing Tool Considered

GitHub issue labels and milestones are GitHub's repository-level classification and planning features, and an App with the Issues permission reads and writes them on a user-owned repository. GitHub issue types and issue fields exist only for organizations. Nothing new is built: the change deletes the board code of the roadmap store and its jobs.

The change deletes `src/devops_cli/roadmap/board_read.py` (its Projects reads for `devops gh project` move to `github/project_read.py`), `src/devops_cli/roadmap/config.py`, `.github/roadmap.toml`, `BoardEntry`, `BoardField`, `FieldOption`, `AddedItem`, `join_items`, `require_job_record_field`, `add_item`, the card read, restore and edit, the board listing cache, the GraphQL budget probe and spend line of the store, `log_round_spend`, `service_pause_until`, the board filters, and the `Job record` field.
