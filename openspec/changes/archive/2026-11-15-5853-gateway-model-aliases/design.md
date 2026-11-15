# Design

## Decisions
- Use LiteLLM router-level `model_group_alias` in `router_settings`: this resolves alias names to group names before deployment selection without adding duplicate entries to `model_list`.
- Keep `model_list` at exactly 17 entries so GPU threshold and matrix consistency checks remain unchanged.
- Map both `:floor` and unadorned OpenRouter model names to the `deepseek-v4.1-flash-1017` group.

## Rejected alternatives
- Duplicating deployments in `model_list`: Rejected because it duplicates health checks, alters weight distribution, and inflates the deployment count.
