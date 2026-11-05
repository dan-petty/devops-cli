# Design

## Decisions

- **Source of the settings.** The DaemonSets `ollama-48gib` and `ollama-64gib` are written by hand, outside the rendered region of `ollama-profiles.yaml`. They are the source of their settings. The render writes only the tiers of the GPU thresholds (`ollama-24gib-embed-gpu0` and `-gpu1` at the tracked thresholds). `devops ai gateway render --apply` is run only to align the windows of the gateway deployments with the new context length of the 64 GiB tier.
- **Context length.** 262144 is the native context length of `qwen3.8:27b`, and the model takes 27 GB at that length on the 48 GiB tier. The 64 GiB tier gets the same length by inference (see Feasibility in the proposal), because the earlier limit of 160000 came from the 70B models, which the tier no longer loads.
- **Routes.** A virtual model that a client names (`devops-coder`, `devops-reasoning`, `devops-review`) keeps its name and takes `qwen3.8:27b`. The groups `qwen3-coder:30b`, `gemma4:31b` and `deepseek-r1:70b` are deleted, because no client in the repository names them. The group `qwen3.8:27b` is the pin of a review for the model of the pool.
- **Fallbacks.** `devops-coder` and `devops-reasoning` run on one deployment, so a fallback from one to the other repeats the same call. Both fall back to `devops-chat`, which also holds the 64 GiB tier.
- **Embeddings.** The render writes an embedding deployment only for an embedding-only tier. A chat tier loads one model for good, and an embedding request would evict it.
- **Default embedding route.** The default Ollama Service is the 48 GiB tier. `DEFAULT_GATEWAY_ROUTES` sends `devops-embedding` to `ollama-24gib-embed-gpu0` through `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL`. A test checks that this Service selects a serving tier that the gateway sends the model to, so a change of the thresholds that renames it fails the test.
- **Implement budget.** `DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW` stays 128000. A step builds its inputs to that budget, and the budget was measured with the earlier model. The tier holds 262144. A larger budget needs its own measurement.
- **Capability gate.** `CONST_MIN_REASONING_MODEL_TIER_B` stays 30. After this change no served model has 30B parameters, so `devops ai gateway failover devops-reasoning` needs `--force`. Lowering the gate is a decision for the owner.

## Rejected Alternatives

- **Keep the embedding model on the large tiers with `OLLAMA_MAX_LOADED_MODELS` 2.** Rejected: the owner asks for no other model, and Ollama unloads the idle model when both do not fit.
- **Delete `devops-reasoning`.** Rejected: `devops-reasoning` is a member of `CONST_AI_GATEWAY_VIRTUAL_MODELS`, of the default ladder tiers and of the capability map. Deleting it is a separate change.
- **Delete the `devops-embedding` route and virtual model.** Rejected: `devops-embedding` is the benchmark default for the gateway provider, and the configured-service-urls spec names it. Pointing its route at an embedding Service keeps both.
- **Lower `LLAMA_ARG_CACHE_RAM` or the memory limit of the 64 GiB tier, or raise them.** Rejected: node `gemini` has 62.5 GiB now and one model needs about 8 GiB, so the present values fit. No measurement supports a change.
