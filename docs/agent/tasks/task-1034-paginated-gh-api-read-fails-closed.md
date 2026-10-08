# Task: Paginated gh api read fails closed on a page that is not the expected json (#1034)

**Issue**: [#1034](https://github.com/dan-petty/devops-cli/issues/1034)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: type/bug, scope/github, priority/p1-high

## Description

`_fetch_all_pages` in `src/devops_cli/github/rate_limiter.py`, used by `run_gh` for all `gh api --paginate` calls, previously failed open on empty responses, non-JSON output, and responses with preambles. This caused bad pages (502 HTML, truncated payloads, error objects) to appear as empty or short listings, potentially allowing PR readiness checks to pass on incomplete data.

The paginated reader is updated to fail closed:
- Validates each page's shape (must be a JSON array or check-runs payload).
- Returns a failed read (`returncode=1`) naming the endpoint and page when a response is empty, malformed, or has an unexpected shape.
- Rejects preamble salvaging via `extract_json_payload`.
- Refuses `--paginate` when combined with `-q`/`--jq`, `-t`/`--template`, `-i`/`--include`, or `--silent` before making requests, naming the incompatible flag in stderr.
- Classifies `gh api graphql --paginate` as a query and refuses it with a message stating that GraphQL queries do not support `--paginate`.
- Injects `per_page=100` into every paginated page URL when omitted, matching GitHub's maximum page size.
- Fails closed naming the page cap when reaching `DEFAULT_GH_MAX_PAGINATED_PAGES` while the listing is still full.
- Updates `_query_timeline_copilot_state` in `pr_monitor.py` to stop using `--jq`, fetching raw JSON and extracting the author from `actor.login` or `user.login`.

## Acceptance Criteria

- [x] A page that exits 0 but is empty, is not JSON, or is not the expected shape is a failed read: `run_gh` returns a non-zero result whose stderr names the endpoint and the page. A literal `[]` page still ends a listing normally.
- [x] `extract_json_payload` is not used to salvage a paginated page: a page with a preamble before its JSON is a failed read.
- [x] Tests through the real `run_gh` with `run_subprocess` stubbed: an HTML page, an empty page, a truncated body and an error object, each on page 1 and on a later page, give a failed read naming the page; a normal listing that ends with `[]` or a short page still succeeds. Offline, each well under 1 s.
- [x] A PR-readiness test: a check-run listing whose second page is malformed makes `devops pr check-readiness` report the read failure instead of evaluating the first page's checks.
- [x] A paged read (`run_gh` with `--paginate`) carrying `-q`/`--jq`, `-t`/`--template`, `-i`/`--include` or `--silent` is refused before any request, exiting non-zero and naming the flag in stderr.
- [x] `_query_timeline_copilot_state` stops using `--jq`, queries `issues/{n}/timeline?per_page=100`, and filters events in Python using `actor.login` or `user.login`.
- [x] Timeline NDJSON fixtures in `tests/test_github_pr_monitor.py` updated to raw JSON array fixtures.
- [x] Test: a two-page timeline whose matching event is on page 2 gives the right Copilot state.
- [x] A listing that is still full when reaching `DEFAULT_GH_MAX_PAGINATED_PAGES` fails closed naming the cap.
- [x] Every page URL carries `per_page`, defaulting to `DEFAULT_GH_REST_PER_PAGE` (100) when omitted.
- [x] `devops gh api graphql --paginate` is classified as a query taking the paged path, and is refused with a message naming GraphQL.
- [x] `changelog.d/1034.md` records the fix under `### Fixed`. `CHANGELOG.md` is not edited.
- [x] `uv run devops ci` passes.
