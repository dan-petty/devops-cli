# Design

## Context

`devops gh rate-limit` displays rate-limit quotas from GitHub.
The command executes `gh api rate_limit` to obtain resource usage statistics.
Before this change, `_parse_rate_limit_payload` invoked `_enrich_rate_limit_resources`.
This enrichment invoked additional REST and GraphQL commands.
The additional commands consumed quota from the user account.

## Goals / Non-Goals

**Goals:**

- Present the rate-limit resources returned directly by `GET /rate_limit`.
- Remove redundant REST and GraphQL calls in `rate_limit_cmd`.
- Delete `_enrich_rate_limit_resources`, `_extract_rest_rate_limit_headers`, and `_extract_graphql_rate_limit`.
- Verify with unit tests that only one `gh api rate_limit` child process starts.

**Non-Goals:**

- Change the rate-limiting algorithm in `src/devops_cli/github/rate_limiter.py`.
- Alter the output schema or table format of `devops gh rate-limit`.

## Decisions

### Decision 1: Use Resources Payload As Returned

`_parse_rate_limit_payload` parses the JSON body returned by `GET /rate_limit`.
It validates that the response contains the `resources` object.
The function returns the parsed data dictionary without modifying the `resources` mapping.

*Alternatives considered:*
- Continuing to query GraphQL for updated points: rejected because `GET /rate_limit` already includes `graphql` resources without spending quota.

### Decision 2: Remove Obsolete Extraction Helpers

Delete `_enrich_rate_limit_resources`, `_extract_rest_rate_limit_headers`, and `_extract_graphql_rate_limit`.
No other modules consume these functions.
Removing them avoids dead code and complies with pre-1.0 development invariants.

*Alternatives considered:*
- Keeping the helpers as deprecated methods: rejected because the repository maintains zero backward-compatibility shims.

### Decision 3: Process Edge Unit Testing

Add tests in `tests/test_gh_cmd.py` that fake `gh` at the process edge via `subprocess.run`.
Assert that `devops gh rate-limit` and `devops gh rate-limit --format json` each invoke `["gh", "api", "rate_limit"]` once.
Assert that the table and JSON outputs include all returned resources.
