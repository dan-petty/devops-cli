# Task 470: Gateway Tuning, Slice 1: Measure Capacity and Cost per Backend, Recommend Weights

**Issue**: [#470](https://github.com/dan-petty/devops-cli/issues/470)
**PR**: [#484](https://github.com/dan-petty/devops-cli/pull/484)
**Status**: In Review
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

Several values in the gateway configuration are maintained by hand and go stale when the cluster
changes: throughput weights, `max_input_tokens`, and one entry per Ollama replica. Deriving the
`devops-review` weights for #467 meant measuring every backend manually. This slice measures
what each backend can do, and what each model costs per request, and recommends weights. It
changes no configuration.

A weight is **capacity ÷ cost**:

- **Capacity**: completion tokens per second with fixed-length replies (`ignore_eos`, honoured
  by vLLM) at the best of several concurrency levels. This is a property of the server and its
  GPUs.
- **Cost**: completion tokens per request when the model stops on its own, on a review-style
  prompt. This is a property of the model. On the same prompt, one model answered in 35 tokens and
  another spent 200 on reasoning.

The first design ranked deployments by requests per second on identical prompts. That mostly
measured how briefly each model answered, and vLLM's prefix cache skipped prompt processing for
every repeat. One backend's rate swung tenfold between runs. Every request now starts with a
unique prefix, and the two quantities are measured separately.

The inference backends admit traffic only from the gateway (the `vllm-perimeter`
NetworkPolicy), so the API server proxy cannot reach vLLM. The sweep therefore runs in an
ephemeral `python:3.14-slim` container attached to the gateway pod
(`kubectl debug --profile=restricted`). The container shares the pod's network identity, so
requests take the same path as the gateway's own, and it runs this project's Python. The LiteLLM
image ships 3.13, which rejects the 3.14 syntax this project's formatter produces. The script is
passed as `python -c`, because `kubectl debug -i` can attach after the container starts and lose
a script piped on stdin.

### Key Deliverables Completed:

- [x] **`devops ai gateway tune`**: discovers a model group's deployments from the gateway's
  authenticated `/model/info`. For each one it reports the engine (vLLM KV-cache capacity from
  `/metrics`, or Ollama), its GPUs (`nvidia-smi` in the backend pod, with memory bandwidth from
  `CONST_GPU_MEMORY_BANDWIDTH_GBPS`), capacity, cost, estimated requests per second, and a
  recommended weight relative to the slowest deployment. Output is a table or JSON, and the
  command is read-only.
- [x] **`devops_cli.ai.gateway_bench`**: the sweep uses only the standard library, since the
  sweep container has none of this project's dependencies.
- [x] **Review-sized prompts**: `--prompt-tokens` defaults to one review page for the analysis
  task's context window, sized as `devops ai review` sizes its pages. Each deployment's prompt is
  capped at 90% of its `max_input_tokens`, as the gateway's pre-call check would.
- [x] **Resilient kubectl calls**: a call that never reached the API server ("Unable to connect
  to the server") is retried, so one transient failure does not abort an eight-minute sweep.
- [x] **`fetch_model_info`**: the gateway's authenticated `/model/info` lookup from #469, now
  public for reuse. Route discovery is built on it.
- [x] **Stable table-width tests**: `output.console` caches one Rich console per process, and
  Rich reads `COLUMNS` only when it builds one. A console built before the per-test fixture set
  `COLUMNS=250` stayed at the 80-column non-terminal default for its whole xdist worker, which
  truncated tables and failed whichever table assertions shared that worker. `conftest.py` now
  sets the terminal when it is imported and resets the cached consoles for each test.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ai_gateway_tune.py`: chat target per backend; unique prompts; fixed-length
    capacity and natural-length cost passes; engine detection; pool discovery; bandwidth lookup;
    backend pod resolution; `nvidia-smi` parsing; the `kubectl debug` flow and its failures; the
    sweep image matching the project's Python; capacity ÷ cost weights in the CLI report.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

A default run (review-sized prompts of 9,830 tokens for a 16K analysis window, `--rounds 1`)
took 8 min 24 s:

| Backend | GPUs | Capacity tok/s | Tokens/request | Est. req/s | Weight → recommended |
|---|---|---|---|---|---|
| vllm | 2x RTX 3090 (102,608 KV tokens) | 24 @ 8 | 121 | 0.20 | 5 → 3 |
| vllm-single | RTX 5070 Ti (20,288 KV tokens) | 48 @ 4 | 118 | 0.41 | 3 → 5 |
| ollama-0 | Quadro P6000 + GTX 1050 Ti | 15 @ 4 | 200 | 0.08 | 1 → 1 |
| ollama-1 | Tesla PG500-216 | 35 @ 8 | 200 | 0.17 | 1 → 2 |

With 1,500-token prompts, the same backends and unique prefixes, the recommendation was
3/32/1/2. The single-GPU vLLM answered in 44 tokens, and prompts that small never loaded the
servers the way review pages do. Hence the review-page default.

## 3. Later Slices

- Cost from real traffic: #474 records the serving backend of each gateway call, and #477 uses
  it. vLLM's lifetime counters cannot stand in: they include every benchmark request.
- No-load capacity estimates from GPU memory bandwidth: #477.
- Render and apply the gateway configuration with rollback: #478.
- Validate recommended weights against real reviews before adopting them: #476.
