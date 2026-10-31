# Design: Migrate github/ Tests to Edge Fakes

## Context
Issue #1307 establishes that tests must double only external process edges and avoid coupling to internal implementation details. Issue #1321 executes Phase E migration for the `github/` package.

## Migration Architecture

### 1. Process and CLI Edge (`process_fake`)
`run_gh` delegates to `run_subprocess([CONST_GH_CLI, ...])`.
When tests use `process_fake: ProcessFake`, calls to `run_subprocess` for `gh` are captured and answered through `process_fake.answer(["gh", ...], ProcessAnswer(stdout=..., returncode=...))`.
No patch on `devops_cli.github.rate_limiter.run_gh` or `run_subprocess` is permitted.

### 2. GitHub Session and REST API Edge (`github_api`)
HTTP requests made through `GitHubSession` or `gidgethub` route to `github_api: GitHubApiFake`.
Routes return canned JSON or text through `github_json` and `github_text`.

### 3. Keyring and Telemetry Edges
- Keyring secrets use `keyring_store: KeyringFake`.
- Spans, metrics, and logs use `otlp: FakeCollector`.

### 4. CLI Runner Invariant
Replace module-level `runner = CliRunner()` with the session-scoped `cli` fixture (`Callable[..., Result]`).

### 5. Test Naming and Anti-Patterns
- Rename functions ending in `_success`, `_failure`, `_basic`, or `_command` to active-voice behaviour statements.
- Remove references to `MagicMock` where direct value comparisons or fakes are appropriate.
- Eliminate private imports of `_`-prefixed names.
