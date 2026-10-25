# Proposal

## Why

Issue #1165 identifies that AI callers fall back to a hard-coded `http://localhost:11434` when no Ollama URL is configured.
This fallback occurs even when another provider is active.
Other service clients also fall back to hard-coded loopback endpoints instead of requiring configuration.
Service clients must dial only configured URLs or connections that the CLI created.

## What Changes

This change alters observable behavior: commands exit with an error naming the missing configuration instead of dialing an unconfigured localhost endpoint.

- Add one AI endpoint resolver that returns endpoints and model aliases for the configured provider.
- Remove hard-coded localhost fallbacks across AI, Qdrant, Tempo, Pyroscope, and Vault callers.
- Remove duplicate Ollama URL constants and keep `DEFAULT_OLLAMA_PORT`.
- Select the AI provider only by configuration and never by URL substrings.
- Change the embedding benchmark to default to the configured embedding model and exit non-zero when all requests fail.
- Update `config.example.yaml` to hold suggested URLs and remove code defaults for service URLs.
- Update `devops k8s deploy-stack` to write deployed service URLs to configuration only when settings are empty.
- Add an ast-grep invariant rule that rejects localhost and loopback string literal fallbacks in `src/`.

This change fits into one pull request.

## Capabilities

### New Capabilities
- `configured-service-urls`: Service clients use only configured URLs and never fall back to an unconfigured localhost default.

### Modified Capabilities

## Impact

- Affected code: `src/devops_cli/ai/`, `src/devops_cli/config/`, `src/devops_cli/commands/`, `src/devops_cli/telemetry/`, and `src/devops_cli/security/`.
- Affected tests: tests that relied on implicit localhost defaults now supply explicit configuration or use test doubles.
- ast-grep invariant checks: new rule `net-localhost-fallback` enforces this invariant project-wide.

## Feasibility

The premise was confirmed against the live codebase:
- `git grep -n -E "https?://(localhost|127\.0\.0\.1)" src/` found hard-coded fallback defaults in `ai/benchmark/`, `ai/rag/`, `ai/client/`, `ai/review/`, `commands/rag.py`, `commands/telemetry.py`, `config/defaults.py`, `config/settings.py`, and `security/vault_broker.py`.
- Running `uv run devops ai test` with an empty configuration attempted a connection to `localhost:11434`.
- Removing code defaults and routing all AI endpoint resolution through a single resolver resolves the problem without backward-compatibility shims.

## Existing Tool Considered

We considered third-party configuration validators.
Pydantic model validation handles field parsing, while `ast-grep` provides structural AST enforcement across `src/`.
Using the existing `ast-grep` engine requires no new dependencies.
The change deletes obsolete duplicate constants `CONST_URL_OLLAMA_LOCALHOST`, `DEFAULT_OLLAMA_BASE_URL`, and hard-coded fallback strings across 17 sites.
