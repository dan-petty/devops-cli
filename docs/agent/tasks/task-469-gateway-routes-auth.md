# Task 469: Gateway Route Discovery Authenticates

**Issue**: [#469](https://github.com/dan-petty/devops-cli/issues/469)
**PR**: [#471](https://github.com/dan-petty/devops-cli/pull/471)
**Status**: In Review
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

`devops ai gateway routes` queried the live gateway only when `--gateway-url` was passed, even
with `ai.gateway_url` configured, and `_fetch_remote_routes` never sent the API key. A LiteLLM
gateway with a master key answered 401, the lookup returned nothing, and the command showed four
built-in default routes that do not describe the gateway. It did not report the failure. The
`ai_gateway_routes` MCP tool runs the same command, so it did the same.

`devops ai gateway status` probes LiteLLM's unauthenticated readiness endpoint and needs no key.

### Key Deliverables Completed:

- [x] **Authenticated Discovery**: `GatewayRouter` takes the AI API key and sends it as a bearer
  token to `/model/info` (and to `/models`, the fallback).
- [x] **Configured Gateway by Default**: `routes` queries `ai.gateway_url` unless
  `--gateway-url` overrides it.
- [x] **Credentials Errors**: a 401 or 403 raises `AICredentialsError`, built by the new shared
  `credentials_error` helper, which the OpenAI-compatible client now uses too. `routes` prints it
  and exits 1, instead of falling back to default routes.
- [x] **Wildcard Deployments Collapsed**: LiteLLM lists a wildcard deployment once for every
  model it can serve, all under the wildcard's deployment id. Those entries collapse into one
  `<provider>/*` route.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ai_gateway.py`: discovery sends the key and collapses wildcard expansions; a
    rejected or missing key raises the credentials error; `routes` uses the configured gateway
    and exits 1 when the key is missing.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

With the key, `devops ai gateway routes` lists the gateway's 12 deployments. The raw
`/model/info` response has 468 entries, most of them wildcard expansions. Without the key, it
exits with "The LLM gateway requires an API key, but no API key is configured (HTTP 401). Set
DEVOPS_CLI_AI_API_KEY or run `devops config set ai.api_key`."
