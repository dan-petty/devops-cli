# Design

## The window sits in the top-level model_info of each deployment

LiteLLM v1.103.0 resolves the window of a deployment in `Router.get_router_model_info`. It starts from the cost-map entry of the backend model, then adds the top-level `model_info` of the deployment. Only a key at that level wins. A key under `litellm_params` is an unknown extra parameter: LiteLLM ignores it.

Every `ollama_chat` deployment sets `model_info.max_input_tokens`. The value is the `OLLAMA_CONTEXT_LENGTH` of its tier. `devops ai gateway render` already aligns every `max_input_tokens` line with the tier, so the value follows the tier without a hand edit. A test holds the values equal to the tiers.

A deployment must set its own value. The router writes the keys of the cost-map schema into one entry for the backend model, and the last deployment registered wins. A deployment that sets no window reads that entry. The measurement showed `devops-background` reading 160000 where its tier holds 128000.

The pinned groups `qwen3-coder:30b` and `gpt-oss:20b` copy the `devops-review` deployments, so they copy the windows too. A pinned review is then routed as the pool routes it.

## Fallbacks

`context_window_fallbacks` has two rules. `devops-chat` goes to `devops-coder` then `devops-reasoning`, and `devops-coder` goes to `devops-reasoning`. The tier `ollama-48gib-fast` has the largest window in the cluster, 262144, and `devops-coder` and `devops-reasoning` run on it. A prompt that no `devops-chat` deployment holds does not fit them either. The rules go, and the key goes with them. A prompt longer than every window gets a `ContextWindowExceededError` that names the window.

The `fallbacks` rules stay. A `devops-review` call that falls back to `devops-background` meets the window 128000 of that tier. A longer prompt now fails with an error, and Ollama no longer cuts it.

## Rejected alternatives

- Drop `gpt-oss:20b` from `devops-review` and set 160000 on the group. The pool would lose a model for no gain. The window of each deployment is enough, and the measurement shows the router applies it per deployment.
- Use the smallest window (131072) as the limit of the group. Every `qwen3-coder:30b` prompt between 131072 and 262144 tokens would fail, though two tiers hold it.
- One `devops-review` group per window class. The clients name `devops-review`, and a caller would have to pick a class. The router already filters the pool by window.
- Point the fallback rules at a larger window. No deployment has a window above 262144.
- Add `litellm` to the dev dependencies to test the router. The package is large and the gateway image pins its own version. The test reads the config shape, and the proposal records the router measurement.
