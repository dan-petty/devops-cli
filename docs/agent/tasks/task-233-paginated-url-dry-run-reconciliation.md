# Task 233: Paginated URL Replacement Loop and Fast Dry-Run Project Reconciliation

**Issue**: [#233](https://github.com/dan-petty/devops-cli/issues/233)
**PR**: [#234](https://github.com/dan-petty/devops-cli/pull/234)
**Status**: In Review
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/github`, `scope/cli`

---

## 1. Description & Objectives

This task addresses performance, reliability, and governance defects across `--dry-run`, GitHub pagination, and PR milestone management:

1. **RFC-Compliant Paginated URL Query Construction (`devops_cli.github.rate_limiter`)**:
   - `_build_paginated_url` previously tested `if 'page=' in endpoint:` which matched `per_page=100` as a substring.
   - The subsequent regex `re.sub(r'([?&])page=\d+', ...)` failed to match `per_page=100`, returning the URL unmodified without adding `&page=2`.
   - In `_run_gh_paginated`, this caused an infinite loop fetching page 1 indefinitely until process termination.
   - Refactor `_build_paginated_url` and `_extract_page_per_page` to use `urllib.parse` (`urlsplit`, `parse_qs`, `urlencode`, `urlunsplit`), ensuring robust parsing and mutation of query parameters.

2. **Fast Dry-Run Project Reconciliation & Persistent Caching (`devops_cli.github.projects`, `rate_limiter`)**:
   - Update `DEFAULT_GH_CACHE_TTL_SECONDS` to 60.0s and enable persistent disk response caching under `.data/cache/responses/`.
   - Enable client-side caching (`use_cache=True`) on `_fetch_repository_issues` and `_fetch_repository_prs` to avoid redundant external network round trips.
   - Optimize PR fetching in `_fetch_repository_prs` to query `state="open"` when extracting linked issue numbers, eliminating pagination through hundreds of closed PRs from history.
   - In `reconcile_project_custom_fields` with `dry_run=True`, only evaluate candidates that are present on the remote project board (`active_items`), ensuring dry-run simulations return in seconds rather than minutes.

3. **PR Milestone Management & Release PR #217 Fix (`devops_cli.commands.pr`, `ai/mcp/server.py`)**:
   - Added `--milestone` (`-m`) option to `devops pr edit` and `pr_edit` FastMCP tool.
   - Added fallback REST PATCH on `/repos/{owner}/{repo}/issues/{number}` when CLI fails.
   - Applied missing milestone `v0.2.19` to release tracking PR #217.

---

## 2. Key Deliverables

- `src/devops_cli/github/rate_limiter.py`: Robust query parsing with `urllib.parse` in `_build_paginated_url` and `_extract_page_per_page`, and persistent disk caching in `_load_disk_cache` / `_save_disk_cache`.
- `src/devops_cli/github/projects.py`: Cached repository issue/PR retrieval, open PR filtering for linked issue resolution, and board item containment in dry run.
- `src/devops_cli/commands/pr.py`: Milestone editing option on `devops pr edit`.
- `src/devops_cli/ai/mcp/server.py`: Milestone parameter on `pr_edit` FastMCP tool.
- `tests/test_github_rate_limiter.py`: Unit tests verifying pagination URL replacement with `per_page` parameters and multi-page responses without infinite loops.
- `tests/test_pr_cmd.py`: Unit test verifying `devops pr edit --milestone`.
