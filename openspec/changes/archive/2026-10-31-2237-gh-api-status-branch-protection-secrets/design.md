# Design

## Overview

Issue #2237 brings 9 `gh` and `status` commands under the owner dry-run rule. Each command gains `@dry_run_class("request-plan")`, declares `--dry-run` where missing, and outputs an ordered sequence of planned requests without sending external HTTP requests or starting child processes.

## Architecture & Module Flow

```
devops gh api / rate-limit / branch-protection / secrets / metrics / status / status
      │
      ▼
   is_dry_run() or --dry-run
      │
      ├── Yes ──► Call request planners (e.g. branch_protection_sync_requests)
      │           └── Return tuple of PlannedRequest objects
      │           └── Output plan via render_request_plan or emit_serialized JSON
      │           └── Exit 0 (zero external network / child processes)
      │
      └── No  ──► Execute real workflow (run_gh, httpx2, etc.)
```

## Detailed Command Plans

1. **`gh api`**:
   - Class: `request-plan`.
   - Planned request: `PlannedRequest(method=method or "GET", target=f"repos/.../{endpoint}", argv=("gh", "api", ...))` matching arguments.

2. **`gh rate-limit`**:
   - Class: `request-plan`.
   - Planned request: `planned_gh(["api", "rate_limit"], "rate_limit")`.
   - Formats: table plan or JSON structure `{"dry_run": true, "requests": [...]}`.

3. **`gh branch-protection audit`**:
   - Class: `request-plan`.
   - Planned requests: For each evaluated branch policy, planned GET for `repos/{repo}/branches/{branch}/protection`.

4. **`gh branch-protection sync`**:
   - Class: `request-plan`.
   - Planned requests: For each branch policy, planned PUT for `repos/{repo}/branches/{branch}/protection` with `--input -` and payload JSON.
   - Eliminates external GitHub API calls during dry run.

5. **`gh metrics`**:
   - Class: `request-plan`.
   - Planned requests:
     - `StoreRequests(repo).every_issue()`
     - `gh run list --repo ... --limit ...`
     - `gh api repos/{repo}/milestones`
     - `gh label list --repo ...`
     - `gh api repos/{repo}/traffic/popular/referrers`
     - `gh api repos/{repo}/traffic/popular/paths`
     - `gh api repos/{repo}`

6. **`gh secrets list`**:
   - Class: `request-plan`.
   - Planned request: `planned_gh(["api", f"repos/{repo}/actions/secrets"], f"repos/{repo}/actions/secrets")`.

7. **`gh secrets sync`**:
   - Class: `request-plan`.
   - Planned requests:
     - `GET repos/{repo}/actions/secrets/public-key`
     - For each secret name: `PUT repos/{repo}/actions/secrets/{name}` with sealed payload placeholder.
   - Eliminates OS Keyring and Vault calls during dry run.

8. **`gh status`**:
   - Class: `request-plan`.
   - Planned request: `PlannedRequest(method="GET", target="GitHub Statuspage summary", argv=("curl", CONST_URL_GITHUB_STATUS_SUMMARY))`.

9. **`status`**:
   - Class: `request-plan`.
   - Planned requests for each target service (`github`, `cloudflare`):
     - `PlannedRequest(method="GET", target=..., argv=("curl", ...))`.

## Gaps Fixture

Remove the 9 command keys from `tests/fixtures/dry_run_gaps.json`:
- `gh api`
- `gh branch-protection audit`
- `gh branch-protection sync`
- `gh metrics`
- `gh rate-limit`
- `gh secrets list`
- `gh secrets sync`
- `gh status`
- `status`
Decreasing remaining gaps from 407 to 398.
