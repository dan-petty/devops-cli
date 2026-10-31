# Design

## Architecture

This change implements request plans and dry-run classifications across 15 GitHub CLI commands in `src/devops_cli/commands/gh.py`, backed by request-plan generator functions in `src/devops_cli/github/projects.py` and `src/devops_cli/github/pages.py`.

### 1. Classification Overview

| Command | Classification | Subsystem Module | Request Plan Details |
| :--- | :--- | :--- | :--- |
| `gh pages build` | `request-plan` | `github.pages` | POST `repos/{repo}/pages/builds` |
| `gh pages builds` | `request-plan` | `github.pages` | GET `repos/{repo}/pages/builds?per_page={limit}` |
| `gh pages status` | `request-plan` | `github.pages` | GET `repos/{repo}/pages` |
| `gh pages verify` | `no-external-request` | `github.pages` | Local file checks only |
| `gh project audit` | `request-plan` | `github.projects` | Board discovery, fields query, view query |
| `gh project link` | `request-plan` | `github.projects` | User login lookup, repo link mutation |
| `gh project list` | `request-plan` | `github.projects` | User login lookup, board listing queries |
| `gh project status` | `no-external-request` | `github.projects` | Template load and panel render only |
| `gh project sync` | `request-plan` | `github.projects` | Board creation / lookup, field provisioning, view sync |
| `gh project template` | `no-external-request` | `github.projects` | Local template file read only |
| `gh project workflows list`| `request-plan` | `github.projects` | Workflow GraphQL query for project |
| `gh views audit` | `request-plan` | `github.projects` | View GraphQL query and layout inspection |
| `gh views list` | `no-external-request` | `github.projects` | Template view table render only |
| `gh views spec` | `no-external-request` | `github.projects` | Template view JSON schema dump only |
| `gh views sync` | `request-plan` | `github.projects` | View creation and rename GraphQL mutations |

### 2. Request Plan Builders

Each request-plan command uses a helper function (e.g. `pages_status_requests`, `pages_builds_requests`, `pages_build_requests`, `project_audit_requests`, `project_link_requests`, `project_list_requests`, `project_sync_requests`, `project_workflows_requests`, `views_audit_requests`, `views_sync_requests`) returning `list[PlannedRequest]`.
Each `PlannedRequest` provides:
- `method`: Subprocess or HTTP action (e.g. `gh`, `gh api`).
- `target`: Human-readable description of the operation.
- `argv`: The exact command-line arguments that `run_gh` or `subprocess.run` executes.
- `condition`: Any prerequisite or condition.

### 3. Dry-Run Option and Output

Each command callback in `src/devops_cli/commands/gh.py` accepts `dry_run: Annotated[bool, typer.Option("--dry-run", ...)] = False`.
When `dry_run or is_dry_run()` is true:
- It calls the corresponding request plan builder without performing external calls.
- If JSON format is requested, outputs a JSON-compatible dictionary with `dry_run: True` and `requests`.
- Otherwise, calls `render_request_plan` to render the numbered list of planned requests.
- Returns early without running external requests.

### 4. Gaps and Ratchet

All 15 command paths are removed from `tests/fixtures/dry_run_gaps.json`, reducing the gap count from 438 to 423. The ratchet test `tests/test_dry_run_class_ratchet.py` enforces that every classified command is removed from the fixture.
