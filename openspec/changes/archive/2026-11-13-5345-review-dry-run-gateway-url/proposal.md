# Proposal: #5345

## Why
The dry-run plan of `devops review path`, `branch`, `pr`, `benchmark`, `corpus score` and `samples validate --review` gets the target of its model request from `_get_review_llm_target` in `src/devops_cli/review/review_plans.py`. When `ai.provider` is `gateway` and `ai.gateway_url` is not set, that function gives a fixed HTTPS host from the source. When `ai.provider` is `ollama` and `ai.ollama_urls` is empty, it gives a localhost address, and `_get_review_embedding_target` does the same for `review corpus generate`. The rule of #1165 allows no service URL that the configuration does not give. Closes #5345.

## What Changes
- The review plan builders get the model endpoint from `resolve_ai_endpoint` (`src/devops_cli/ai/endpoints.py`), the resolver that the review run uses before it makes its model client. The model request uses the `analysis` task, as the review run does.
- When the resolver refuses because a setting is not set, the plan target names that setting as a placeholder, for example `<ai.gateway_url>/chat/completions`. The dry run still makes zero requests and exits 0. The real run stops with the error of the resolver, as before.
- The fixed gateway host and the two localhost fallbacks go out of the module.
- The gateway target is `<ai.gateway_url>/chat/completions`. The old target added `/v1` to the configured URL, so a configured `https://gateway.example.com/v1` gave `/v1/v1/chat/completions`. The model client uses `ai.gateway_url` as its base URL with no more `/v1`.
- The Anthropic target is `<base>/v1/messages`, the path of the Messages API, in place of an OpenAI path.

The dry-run output is behavior that a person observes, so the change has a spec delta. The change fits one pull request.

## Capabilities
- `configured-service-urls` (modified): ADDED requirement "A review dry run takes its model endpoint from the configuration".

## Impact
- The dry-run plan of the review commands names the configured endpoint, or the setting that is not set. No setting, no dependency and no real run changes.
- `src/devops_cli/ai/ai_plans.py` keeps nine localhost fallbacks of the same kind, and the guard of #1165 does not match a fallback in a list. #5395 holds that work.
- Rollback: `git revert`. No downtime.

## Feasibility
- `git show origin/main:src/devops_cli/review/review_plans.py` at release 0.127.0: line 24 is `gw = (settings.ai.gateway_url or "https://<fixed-host>").rstrip("/")`, and lines 21 and 35 fall back to `["http://localhost:11434"]`.
- With a config file that holds only `ai.provider: gateway`, `DEVOPS_CLI_CONFIG=<file> uv run devops review path src --dry-run` on the worktree at `origin/main` printed `POST https://<fixed-host>/v1/chat/completions`. With `ai.gateway_url: https://gateway.example.com/v1`, it printed `POST https://gateway.example.com/v1/v1/chat/completions`. With only `ai.provider: ollama`, it printed `POST http://localhost:11434/api/chat`.
- The guard of #1165 is the ast-grep rule `net-localhost-fallback` (`.ast-grep/rules/net-localhost-fallback.yml`). It reads every file under `src/`, this module too, so no file list needs a change. `uv run ast-grep scan --rule .ast-grep/rules/net-localhost-fallback.yml src/devops_cli/review/review_plans.py` found nothing on `origin/main`: the rule matches `or "http://localhost..."` and not `or ["http://localhost..."]` or a host that is not loopback. `git grep -n 'or \["https\?://localhost' src` finds 11 such sites: 2 in this module and 9 in `src/devops_cli/ai/ai_plans.py`.
- `resolve_ai_endpoint` raises `ConfigurationError` with `key="ai.gateway_url"` for a gateway with no URL and `key="ai.ollama_urls"` for Ollama with no URL (`tests/ai/test_service_client_configured_urls.py`). `_make_review_clients` in `src/devops_cli/ai/review/runner.py` calls it with the `analysis` task before the review run makes its client.
- `OpenAIClient._openai_client` (`src/devops_cli/ai/client/openai.py`) gives `ai.gateway_url` to the OpenAI SDK as `base_url`, and the SDK posts a chat to `<base_url>/chat/completions`.

## Existing Tool Considered
- The project resolver `resolve_ai_endpoint` covers the need, and the change uses it in place of the copy of the provider rules in the module. No open tool resolves the endpoints of the devops-cli settings.
- Internal code that the change deletes: the provider branches of `_get_review_llm_target` and `_get_review_embedding_target`, with their fixed host and localhost fallbacks.
