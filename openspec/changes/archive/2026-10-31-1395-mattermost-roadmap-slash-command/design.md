# Design

## Context

See `proposal.md` for motivation. The roadmap service webhook router handles incoming deliveries and checks headers, body sizes, and exposures. Issue #1395 adds the Mattermost provider for slash commands.

## Goals / Non-Goals

**Goals:**
- Provide synchronous `/roadmap` command status replies in Mattermost.
- Validate request authorization with an `Authorization: Token <token>` header.
- Report status per repository and per lane using in-memory worker state.
- Keep the roadmap service deployment at zero replicas.

**Non-Goals:**
- Support write operations or triggers from chat.
- Query GitHub API during command handling.
- Deliver responses through asynchronous `response_url`.

## Decisions

### Decision 1: Use router responder mode instead of asynchronous response
The Mattermost provider registers a synchronous responder function in the router.
- *Rationale*: Status inquiries read existing memory state and finish in milliseconds. Mattermost times out after 3 seconds, which is ample time for an in-memory lookup.
- *Rejected Alternative*: Asynchronous response via `response_url`. Rejected because `response_url` routes to the public domain behind Cloudflare Access, which the cluster cannot resolve or reach directly.

### Decision 2: Add AuthorizationToken verifier to the router
Implement `AuthorizationToken(scheme="Token")` in `src/devops_cli/server/routes/webhooks.py`. It uses `get_authorization_scheme_param` and `secrets.compare_digest`.
- *Rationale*: Verifies bearer/token style authorization headers securely with constant-time equality checks.
- *Rejected Alternative*: Query parameter or form token verification. Rejected because headers keep secret tokens out of query logs and URL strings.

### Decision 3: Form URL-encoded parsing with 415 on JSON
Mattermost slash commands post payloads as `application/x-www-form-urlencoded`. The router checks the `Content-Type` header: form payloads are parsed via `request.form()`, while JSON payloads return HTTP 415.
- *Rationale*: Matches Mattermost slash command specifications.
- *Rejected Alternative*: Accept any content type. Rejected because strict content negotiation prevents payload misinterpretation.

### Decision 4: Read-only ServiceManager status method
`RepoWorker` tracks round start, end, and result. `ServiceManager` exposes a public read-only status method that returns lane and worker execution status.
- *Rationale*: Encapsulates worker internals behind `ServiceManager`, enabling clean architectural decoupling.
- *Rejected Alternative*: Direct access to `RepoWorker` instances from router. Rejected because exposing worker references breaks encapsulation and complicates future Argo workflow migrations.

## Risks / Trade-offs

- [Token configuration missing] → If `mattermost.command_token` is unset, the router logs a warning and returns HTTP 401 without exposing secret values.
- [Service offline] → The service runs at `replicas: 0` until operational deployment. Tests exercise the full router and responder stack via `TestClient`.

## Migration Plan

No data migration required. Manifest changes take effect on next Argo CD sync.
