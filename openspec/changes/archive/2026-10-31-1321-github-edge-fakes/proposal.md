# Proposal

## Why

Issue #1321 completes Phase E of the test harness refactoring for the `github` domain (#1307). Tests covering `github/` modules previously relied on internal monkeypatching of `run_gh`, `run_subprocess`, and functions in `github/`, imported private `_`-prefixed symbols, and constructed hand-rolled mocks or doubles instead of using the shared edge fakes. This change migrates `github/` tests to edge fakes (`process_fake`, `github_api`, `keyring_store`, `otlp`, and `cli`), removes internal patches, and cleans up test anti-patterns.

## What Changes

- Replace internal patches to `run_gh`, `run_subprocess`, and `devops_cli` symbols with `process_fake` and `github_api`.
- Replace private `_`-prefixed imports with public interface calls or test helpers.
- Replace manual keyring and telemetry mocks with `keyring_store` and `otlp` fixtures.
- Replace module-level `runner = CliRunner()` instances with the `cli` fixture.
- Rename test functions ending in `_success`, `_failure`, `_basic`, or `_command` to active-voice behaviour statements in ASD-STE100 terms.
- Preserve coverage above 90% across `src/devops_cli/github/` and pass all CI checks.
- This change alters no consumer-observed CLI behavior or commands, so it sets `skip_specs: true`.
- This change fits one pull request.

## Feasibility

The shared fakes already exist in `tests/support/fakes/`:
- `ProcessFake` (`process_fake` fixture) scripts child processes through the process seam, including `gh` and `git`.
- `GitHubApiFake` (`github_api` fixture) fakes GitHub's REST API at the HTTP edge for the GitHub session.
- `KeyringFake` (`keyring_store` fixture) fakes OS keyring storage.
- `FakeCollector` (`otlp` fixture) collects spans, metrics, and logs.
- `cli` fixture provides an isolated Click/Typer runner.
All edge fakes are verified in the codebase and used across existing contract and edge suites.
`src/devops_cli/github/metrics.py` already routes `git` calls through `run_subprocess`.

## Existing Tool Considered

- `ProcessFake` from #775 provides process runner isolation for `gh` and `git`.
- `GitHubApiFake` from #983 provides GitHub REST API interception for session requests.
- `FakeKeyring` from #1318 provides OS keyring isolation.
- `FakeCollector` from #1319 provides OpenTelemetry collection.
- Building custom test doubles instead would add significant token and maintenance cost. Reusing existing shared fakes maintains harness consistency and ensures fast execution.
