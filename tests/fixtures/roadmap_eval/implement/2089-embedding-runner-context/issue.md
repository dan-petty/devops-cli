### What happened

On 2026-10-24, `kubectl -n llm exec ds/ollama-48gib-slow -c ollama -- ollama ps` showed `qwen3-embedding:0.6b` loaded with the context 32768 and the size 5.2 GB, with the expiry `Forever`.

The gateway sends `num_ctx: 8192` with each embedding call to this tier (`k8s/llm/gateway/config.yaml`). Its comment says that without it, Ollama loads the embedder with 32,768 tokens: 5.2 GB, not 2.9 GB. So a call that sent no `num_ctx` loaded this runner, and the tier keeps every runner loaded for good (`OLLAMA_KEEP_ALIVE: "-1"`, #1064). The runner holds about 2.3 GB more VRAM than the plan, on the tier that also keeps `qwen3.8:27b` loaded.

### What should happen

The embedding runner on ollama-48gib-slow loads with the context 8192, or with the context of the plan. Find the caller that loads it without `num_ctx`, for example `devops ai prewarm`, a direct embedding call, or the LiteLLM health check of the embedding deployment. Fix it at that caller, then check `ollama ps` again.

### Evidence

- `ollama ps` on ollama-48gib-slow (read-only), 2026-10-24: `qwen3-embedding:0.6b  5.2 GB  100% GPU  32768  Forever`.
- ollama-48gib-slow sets `OLLAMA_CONTEXT_LENGTH: "128000"`, so a call that sends no `num_ctx` gets the model's full context, 32768.
- The order-2 embedding deployment of ollama-48gib-slow sends `num_ctx: 8192`.

### Scope

Find the caller first. Do not change the tier's keep-alive.
