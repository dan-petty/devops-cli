# Design

## Overview

Issue #2234 brings 17 `pr` commands under the owner dry-run rule. Each command gains `@dry_run_class("request-plan")`, declares `--dry-run` where missing, and outputs an ordered sequence of planned requests without sending external HTTP requests or starting child processes.

## Architecture & Module Flow

```
devops pr <subcommand>
      │
      ▼
   is_dry_run() or --dry-run
      │
      ├── Yes ──► Call request planners in devops_cli.github.pr_plans
      │           └── Return tuple of PlannedRequest objects
      │           └── Output plan via render_request_plan or emit serialized JSON
      │           └── Exit 0 (zero external network / child processes)
      │
      └── No  ──► Execute real workflow (run_gh, GhCliClient, etc.)
```

## Detailed Command Plans

1. **Argument Builders**:
   - `pr_list_args(state, limit, repo)`: builds CLI argument vector for `gh pr list`.
   - `pr_view_args(number, repo)`: builds CLI argument vector for `gh pr view`.
   - `pr_edit_args(number, base, title, body, repo, milestone)`: builds CLI argument vector for `gh pr edit`.
   - `pr_create_args(title, body, base, repo)`: builds CLI argument vector for `gh pr create`.
   - `pr_ready_args(number, repo)`: builds CLI argument vector for `gh pr ready`.
   - `pr_diff_args(number, color, repo)`: builds CLI argument vector for `gh pr diff`.
   - `pr_close_args(number, comment, delete_branch, repo)`: builds CLI argument vector for `gh pr close`.
   - `unresolve_thread_args(thread_id)`: builds GraphQL mutation argument vector for `unresolveReviewThread`.

2. **Planned Requests**:
   - Every request uses `PlannedRequest` specifying `method`, `target`, and `argv`.
   - Polling commands (`pr monitor`, `pr wait`) declare `repeat="every <interval>s up to <timeout>s"`.
   - Branch discovery or optional steps declare clear conditions (e.g. `condition="the pull request opens"`).

3. **Output Formatting**:
   - Formats supporting structured JSON (`pr monitor`, `pr wait`, `pr hardening-report`, `pr threads list`) return JSON dictionaries containing `dry_run: true` and planned requests.
   - Text formats render plans with `render_request_plan`.
