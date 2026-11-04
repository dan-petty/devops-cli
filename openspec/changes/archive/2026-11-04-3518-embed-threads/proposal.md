## Why

Each embedding-only instance uses 12 CPU cores under load, and the work runs on its GPU (#3518). `llama-server` starts with its default thread count, and its threads spin.

## What Changes

- `devops ai gateway render` sets `LLAMA_ARG_THREADS: "1"` for a tier at or below `embedding_only`, and `ollama-24gib-embed-gpu0` and `-gpu1` get it. A manifest changes, so the change carries a spec delta.
- The gateway comment says why embeddings keep `simple-shuffle`, and the profiles, `k8s/README.md` and the knowledge base give the measured numbers.

It fits one pull request.

## Feasibility

Measured on 2026-11-04 on `ollama/ollama:0.40.12` with one Quadro P6000, a batch of 32 chunks of about 300 tokens, and CPU from the cgroup `cpu.stat`, in two rounds:

- `num_thread` default: 1.69 s, 20.7 core-seconds per batch, 12.2 cores. `num_thread` 1: 1.70 s, 2.0 core-seconds, 1.2 cores. 2, 4, 8 and 16 give the same time, with 2.8, 4.5, 7.8 and 14.2 core-seconds.
- `LLAMA_ARG_THREADS=1` in a temporary Ollama pod: 1.69 s, 2.0 core-seconds, 1.2 cores, and `ollama ps` shows 100% GPU.
- Vectors with `num_thread` 1 and the default are exactly equal, for 34 inputs.
- A temporary LiteLLM pod with the image of the gateway, and one model group for each strategy on the same two instances: `least-busy` sent 72 of 72 batches to the first deployment at each of 2, 4 and 8 streams, and gave 0.55 batches a second. `simple-shuffle` gave 0.85 to 1.08. So the gateway keeps `simple-shuffle`.

## Existing Tool Considered

`LLAMA_ARG_THREADS` is an environment variable of `llama-server`, the runner of Ollama, as `LLAMA_ARG_CACHE_RAM` already is for `ollama-64gib`. The change builds nothing, and it deletes no internal code.
