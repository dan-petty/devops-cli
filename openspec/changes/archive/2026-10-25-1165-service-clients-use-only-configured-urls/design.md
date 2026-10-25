# Design

## Context

See proposal.md - Why.
Clients currently use default strings or fallback expressions when configuration settings are empty.
This creates silent network dials to loopback ports that might not exist or that belong to other services.

## Goals / Non-Goals

**Goals:**
- Provide a single AI endpoint resolver function that resolves the URL and model aliases for the active provider.
- Raise strongly typed `ConfigurationError` whenever required service URLs are not configured.
- Remove all implicit loopback defaults and duplicate URL constants.
- Guard the repository with an ast-grep invariant rule that prevents new localhost fallback literals in `src/`.

**Non-Goals:**
- Removing cluster-internal in-cluster Service names used by deployment manifests.
- Altering the loopback addresses created dynamically by active port forwards.

## Decisions

### 1. Centralized AI endpoint resolver in `src/devops_cli/ai/endpoints.py`
A new module `src/devops_cli/ai/endpoints.py` exports `resolve_ai_endpoint(config, task=None)`.
When the provider is `gateway`, the resolver returns `ai.gateway_url` and `CONST_AI_GATEWAY_VIRTUAL_MODELS`.
When the provider is `ollama`, the resolver returns the configured `ai.ollama_urls`.
If the active provider lacks a URL, the resolver raises `ConfigurationError` naming the setting to set.
*Alternative considered:* Let each caller check its own settings.
*Evidence rejecting alternative:* The fallback appeared across 17 different sites in `src/` because callers duplicated resolution logic.

### 2. Service URL fields default to None in Settings
In `src/devops_cli/config/settings.py`, `qdrant.url`, `tempo.url`, `pyroscope.url`, `ai.gateway_url`, and `ai.portkey_url` default to `None`.
`ai.ollama_urls` defaults to an empty list.
Suggested values move to `config.example.yaml`.
*Alternative considered:* Keep default localhost URLs in code.
*Evidence rejecting alternative:* Issue #1165 showed benchmark commands attempted connections to `localhost:11434` despite `ai.provider: gateway` being configured.

### 3. Deploy-stack updates empty settings only
`devops k8s deploy-stack` inspects the active settings after deploying workloads.
If a deployed service URL setting is empty, `deploy-stack` saves the detected URL and prints the change.
If a setting already has a value, `deploy-stack` preserves it.
`--dry-run` reports these writes under `config_writes` and executes no requests.
*Alternative considered:* Run `configure-urls` automatically with overwrite.
*Evidence rejecting alternative:* Overwrites user-specified custom endpoints or remote tunnel addresses.

### 4. ast-grep invariant rule `net-localhost-fallback`
The rule matches string literals matching `http(s)://(localhost|127.0.0.1)` in `or` expressions, dictionary `.get()` defaults, and `getattr()` defaults in `src/`.
*Alternative considered:* Rely on manual code reviews.
*Evidence rejecting alternative:* Fallback literals reappeared at 17 sites despite previous refactoring efforts.

## Risks / Trade-offs

- [Commands fail when users have no configuration file] → Users must configure URLs or copy `config.example.yaml`. Clear error messages tell the user which command to run (e.g. `devops config set ai.ollama_urls ...`).
- [Existing tests that instantiated `LLMClient` with empty config fail] → Tests provide explicit configurations or use `set_llm_client_override`.
