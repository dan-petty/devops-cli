# Design

## Problem Statement

Sixteen commands make external requests to GitHub or other services without returning a planned sequence of operations under `--dry-run`:
- `gh issues create`
- `gh issues edit`
- `gh issues list`
- `gh issues status`
- `gh issues triage`
- `gh labels audit`
- `gh labels list`
- `gh labels sync`
- `gh milestones close`
- `gh milestones edit`
- `gh milestones list`
- `gh milestones status`
- `gh runs list`
- `gh runs view`
- `roadmap run`
- `survey`

Running these commands with `--dry-run` either executes external calls, reports `No such option: --dry-run`, or prints an unhelpful delegation preview.

## Architecture & Implementation Strategy

### 1. Request Plan Builders
Construct request builders in their respective modules that return `PlannedRequest` instances:
- In `src/devops_cli/github/issues.py`:
  - `create_issue_args` and `create_issue_requests`
  - `issues_list_args` and `issues_list_requests`
  - `issues_status_requests` (reusing `StoreRequests(repo).every_issue()`)
  - `issues_triage_requests` (reusing `StoreRequests(repo).every_issue()`)
  - `issues_edit_requests`
- In `src/devops_cli/github/labels.py` and `gh.py`:
  - `labels_list_args` and `labels_list_requests`
  - `audit_labels_args` and `audit_labels_requests`
  - `sync_labels_requests`
- In `src/devops_cli/roadmap/request_plan.py` and `gh.py`:
  - `milestones_list_requests`, `milestones_status_requests`, `milestones_close_requests`, `milestones_edit_requests`
- In `src/devops_cli/github/run_view.py` and `gh.py`:
  - `runs_list_args` and `runs_list_requests`
  - `runs_view_requests`
- In `src/devops_cli/commands/roadmap.py`:
  - `roadmap_run_requests`
- In `src/devops_cli/commands/survey.py`:
  - `survey_requests`

### 2. Command Decorations & Handlers
In `src/devops_cli/commands/gh.py`, `src/devops_cli/commands/roadmap.py`, and `src/devops_cli/commands/survey.py`:
- Decorate each command with `@dry_run_class("request-plan")`.
- Add `dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False` where missing.
- When `dry_run or is_dry_run()` is true, construct planned requests and either:
  - If structured format (JSON) is requested, emit `{"dry_run": True, "requests": [r.__dict__ for r in planned]}`.
  - Otherwise, render with `render_request_plan` or `render_dry_run`.
  - Return early without executing any network or subprocess calls.

### 3. Gap List Updates
Remove all 16 command entries from `tests/fixtures/dry_run_gaps.json`. Keep the file sorted lexicographically without duplicates.

### 4. Tests
Create `tests/test_gh_issues_milestones_labels_runs_dry_run.py` to verify:
- Class declarations (`request-plan`) for all 16 commands.
- Removal of the 16 commands from `dry_run_gaps.json`.
- Zero external requests executed under `devops <cmd> --dry-run` and `devops --dry-run <cmd>`.
- Structured JSON output returns `dry_run: True` and planned requests.
- Planned request arguments match the real dispatched command arguments.
