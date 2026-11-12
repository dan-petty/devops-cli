# Proposal: #4825

## Why

Issue #4825: the module `src/devops_cli/server/routes/stream.py` served two routes, `GET /v1/stream/events` (SSE) and `/v1/ws/reasoning` (WebSocket). Both sent the same four canned events for each persona. The last event said "Zero-trust security invariants verified. No unvalidated egress found.", but no check ran before it. A client could think that a security check passed. Only the tests called the routes.

## What Changes

- Delete `src/devops_cli/server/routes/stream.py` with its two routes, the `StreamEvent` model and the canned event generator.
- Delete the router wiring in `src/devops_cli/server/app.py`.
- Delete `DEFAULT_STREAM_PERSONA` and `DEFAULT_ALLOWED_STREAM_PERSONAS` from `src/devops_cli/config/defaults.py`.
- Delete `tests/server/test_server_stream.py` and the row of the deleted file in `tests/fixtures/swallowed_failures_ceilings.json`.
- Add a test that the app serves neither path and that its OpenAPI schema lists neither path.
- Change the knowledge base line about `devops_cli.server`, which named an SSE event stream.
- The REST API is a service behavior that a client sees, so the change has a spec delta: a new capability `service-rest-routes`.

## Capabilities

- `service-rest-routes` (new): the routes of the Service REST API, and that the API serves no canned reasoning feed.

## Impact

- A client of `/v1/stream/events` or `/v1/ws/reasoning` gets 404. No code, manifest, document or test outside the deleted files called the routes.
- The deleted files hold 1 swallowed-failure site (`except Exception` in the WebSocket route), so the ceiling fixture loses its row.

## Feasibility

- `git grep -n -E "stream/events|ws/reasoning|STREAM_PERSONA|routes\.stream"` on `origin/main` (87ae9eefa) found the routes only in `stream.py`, `app.py`, `defaults.py`, `tests/server/test_server_stream.py` and the ceiling fixture.
- `stream.py` lines 35-57 build the four events from a fixed list, and the two routes only pick a persona name from the allowlist. No other code runs.
- No open pull request changes these files (REST list of the 24 open pull requests on 2026-11-12).
- The owner accepted the delete on 2026-11-11 (#4780).

## Existing Tool Considered

- A delete. No tool applies. Cost: about 20,000 tokens and 0.5 hours.
- Internal code that the change deletes: `src/devops_cli/server/routes/stream.py` (110 lines), `tests/server/test_server_stream.py` (78 lines), and 2 constants in `defaults.py`.
