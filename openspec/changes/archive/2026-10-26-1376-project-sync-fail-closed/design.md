# Design

## Context

See proposal.md - Why.
GitHub Projects v2 operations run through gh CLI subprocess commands and GraphQL queries.
Reconcile operations already use `FieldListingPayload` and `_require_whole` to prevent partial reads.
Field provisioning, board lookups, and project listings previously caught failures and returned defaults.

## Goals / Non-Goals

**Goals:**
- Fail closed when board field listings or board lookups fail.
- Route non-zero gh exits in provisioning and linking through `classify_gh_failure`.
- Distinguish non-existent boards from read failures in lookup functions.
- Restrict owner cache population to the authenticated GitHub user.
- Ensure project listings raise errors rather than reporting zero boards.

**Non-Goals:**
- Add retry loops beyond existing rate limiter retry policies.
- Alter field value reconciliation logic.
- Support deprecated GitHub Projects classic boards.

## Decisions

### Decision 1: Use `FieldListingPayload` and `field_list_args` for field reads
- *Rationale*: Reconcile uses `FieldListingPayload` with totalCount validation. Using the same parser prevents code drift and enforces full responses.
- *Alternatives considered*: Keep `_fetch_existing_fields_by_name` and add custom validation. Rejected because duplicate parsers increase maintenance cost and diverge in error handling.

### Decision 2: Distinguish 404 from unread errors in board lookups
- *Rationale*: HTTP 404 indicates the requested entity does not exist. HTTP 500, network drop, or invalid JSON indicate read failures. Raising `GitHubUnreadError` on read failures prevents duplicate board creation.
- *Alternatives considered*: Return `None` on all lookup errors. Rejected because network glitches create duplicate project boards.

### Decision 3: Route field creation and linking failures through `classify_gh_failure`
- *Rationale*: CLI exit status and stderr carry specific error categories such as missing scopes (`GitHubScopeError`). Classifying failures allows precise user guidance.
- *Alternatives considered*: Raise unclassified `GitHubOperationError` directly. Rejected because users cannot identify missing token scopes.

### Decision 4: Only cache `@me` when owner matches authenticated user
- *Rationale*: If an organization board query fails, `@me` points to the user account instead of the organization. Caching `@me` for organizations corrupts subsequent commands.
- *Alternatives considered*: Clear cache after each command. Rejected because valid user resolution benefits from caching across calls.

## Risks / Trade-offs

- [Commands fail instead of continuing with partial state] → Operations fail closed to protect board data integrity.
- [Tests that expect None on HTTP 500 must expect GitHubUnreadError] → Update existing tests to assert typed errors.
