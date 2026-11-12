# Design

## Decisions

- Delete the whole module `stream.py`, not only `GET /v1/stream/events`. The WebSocket route `/v1/ws/reasoning` sends the same canned events from the same generator, so it has the same defect. The issue names the persona allowlist and the module tests, and only these two routes use them.
- Delete with no shim and no redirect. The project is alpha before 1.0.0, and no caller exists.
- The new test reads the route table, a request and the OpenAPI schema of `create_app()`, so a route that comes back under one of the two paths makes the test fail.

## Rejected alternatives

- Connect the feed to a real review run. No caller asks for a live reasoning feed, and `devops ai chat` already streams the reasoning of a real run in the terminal. To build a feed is new work for a new issue.
- Keep the routes and remove only the "verified" event. The other three events are also canned text, and they also say that work ran ("Parsing AST structure...") when no work ran.
