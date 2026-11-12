# Tasks

## 1. The REST API serves no canned reasoning feed

Kind: behavior. Changes: `tests/server/test_server.py`, `src/devops_cli/server/routes/stream.py`, `src/devops_cli/server/app.py`, `src/devops_cli/config/defaults.py`, `tests/server/test_server_stream.py`, `tests/fixtures/swallowed_failures_ceilings.json`.

- [x] 1.1 Write the failing test: the app answers `GET /v1/stream/events` with 404, and neither the OpenAPI schema nor the route table holds a `/v1/stream` or `/v1/ws` path.
  - Verification: `$ uv run devops ci test tests/server/test_server.py`
- [x] 1.2 Delete `stream.py`, its router wiring, the two persona constants, `tests/server/test_server_stream.py` and the ceiling row of the deleted file.
  - Verification: `$ uv run devops ci test tests/server/`

## 2. Documents

- [x] 2.1 Change the `devops_cli.server` line of the knowledge base page `python_packages.md`, which named an SSE event stream.
  - Verification: `! git grep -n -i -E "stream/events|ws/reasoning|STREAM_PERSONA|routes\.stream|SSE event stream" -- src docs README.md ARCHITECTURE.md`
