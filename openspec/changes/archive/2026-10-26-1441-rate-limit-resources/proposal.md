# Proposal

## Why

In #1441, `devops gh rate-limit` reads the GitHub `GET /rate_limit` endpoint.
The command then calls `_enrich_rate_limit_resources` to overwrite `core` and `graphql` rate limit values.
This enrichment sends a `GET /user -i` request that spends from the core REST quota.
It also runs a GraphQL `rateLimit` query that spends from the GraphQL quota.
GitHub documentation confirms that `GET /rate_limit` does not spend from the REST quota.
GitHub documentation also confirms that the endpoint provides `graphql` quota resources.
The enrichment consumes quota during rate-limit checks.

## What Changes

- Delete `_enrich_rate_limit_resources`, `_extract_rest_rate_limit_headers`, and `_extract_graphql_rate_limit` from `src/devops_cli/commands/gh.py`.
- Keep the untouched resources dictionary returned by the `GET /rate_limit` endpoint in `_parse_rate_limit_payload`.
- Add unit tests verifying that `devops gh rate-limit` and `devops gh rate-limit --format json` start exactly one child process.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/gh.py`: removes extraneous API calls and unused helper functions.
- `tests/test_gh_cmd.py`: adds process-edge tests asserting single child process execution and resource printing.

## Feasibility

- Verified `uv run devops gh api rate_limit` against GitHub API. The endpoint returns both `core` and `graphql` quota values in `resources`.
- Verified GitHub documentation stating that `GET /rate_limit` does not spend REST rate limit quota.
- Verified that `_enrich_rate_limit_resources`, `_extract_rest_rate_limit_headers`, and `_extract_graphql_rate_limit` are not referenced outside `src/devops_cli/commands/gh.py`.

## Existing Tool Considered

GitHub CLI (`gh`) and the GitHub REST API provide rate-limit tracking.
The command already uses `gh api rate_limit`.
Removing internal enrichment calls ensures the tool uses the upstream endpoint directly.
