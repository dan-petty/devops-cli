# Design

## Decisions
- **One resolver.** The plan builders call `resolve_ai_endpoint`, the resolver that the review run calls in `_make_review_clients`. The model request uses `task="analysis"`, so a task override of the provider or the endpoint (`ai.tasks.analysis`) shows in the plan, as it does in the run. The embedding request of `review corpus generate` uses the global AI settings, as before.
- **A missing setting is a placeholder in the plan.** When the resolver raises `ConfigurationError`, the plan target starts with `<{key}>`, the setting that the error names, such as `<ai.gateway_url>`. A dry-run plan shows a value that it does not have as a named placeholder (`src/devops_cli/dry_run/requests.py`), and the Argo CD plans do the same for an unset `argocd.url` (`https://<argocd-url>`). The error is not hidden: the plan names its setting, and the real run stops with the same error.
- **The path follows the provider.** Ollama gets `/api/chat` and `/api/embeddings`. Claude gets `/v1/messages`, because the resolver gives the API root `https://api.anthropic.com`. Every other provider gets `/chat/completions` and `/embeddings` after the resolved base, which already holds `/v1` where the provider needs it.

## Rejected alternatives
- **Stop the dry run with the error of the resolver.** The real run of `review corpus generate` makes no model request and needs no AI setting, but its plan lists an embedding request. An error in the plan builder would make that dry run fail where the real run passes. `devops ai benchmark` also does not resolve the endpoint under `--dry-run` (`src/devops_cli/commands/benchmark.py`).
- **Keep a default host for the gateway.** The rule of #1165 refuses a service URL that no setting gives, and `tests/config/test_service_url_defaults.py` holds `ai.gateway_url` to no code default.
- **Fix `src/devops_cli/ai/ai_plans.py` and extend the ast-grep rule in this change.** The issue names one module. The other module has nine sites and its own plans, and a rule change that matches a fallback in a list fails the scan until all nine are gone. The follow-up issue holds both.
