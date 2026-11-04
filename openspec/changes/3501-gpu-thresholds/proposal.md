## Why

Embedding calls wait but do not fail (#3501). In 72 h, the gateway answered 4,715 `/v1/embeddings` calls with 200 and none with a failure. In 48 h, `ollama-48gib` answered embeddings with a p95 of 37 s and a maximum of 60 s, because the tier also serves chat models. `ollama-48gib-slow` was an order 2 target, held a chat model of 22 GB, and ran one Ollama instance on two GPUs. Nothing stated which GPU architectures are too old for chat, or which must run one instance per GPU.

## What Changes

- `k8s/llm/profiles/gpu-thresholds.yaml` holds two values of `nvidia.com/gpu.architecture`, `embedding_only` and `per_gpu`, both `pascal`.
- `devops ai gateway render` also writes the tiers of `k8s/llm/profiles/tier-templates/` into marked regions of the profiles, the services and the gateway config, and takes `--thresholds` and `--tier-templates`. A test fails when the regions differ from its output.
- `ollama-48gib-slow` becomes `ollama-24gib-embed-gpu0` and `-gpu1`: each claims one GPU, serves the embedding model alone, and has its own Service and order 1 gateway deployment. The Service `ollama-48gib-slow` goes away.
- The embedding deployments of `ollama-48gib-fast` and `ollama-64gib-standard` move to order 2, and the one of `ollama-16gib-fast` to order 3.
- `devops-background` moves to `ollama-64gib-standard`, with a window of 160000.

A command, a manifest and a route change, so the change carries a spec delta. It fits one pull request.

## Feasibility

Measured on 2026-11-04 on `ollama/ollama:0.40.12` with temporary pods on a node with two Quadro P6000 GPUs, and device plugin 0.16.2:

- Two pods with `nvidia.com/gpu: 1` each saw one GPU, each a different UUID, in `nvidia-smi -L`. The live tiers claim no GPU, so the device plugin had both free.
- A batch of 32 chunks (12,886 tokens) took 2.1 s, or 3.9 s with a cold model. `ollama ps` showed 1.3 GB of VRAM, and peak container memory was 890 MiB.
- One instance gave 0.50 batches a second, with a longest wait of 8.0 s at 4 streams. Two instances gave 0.99, with a longest wait of 4.2 s.
- `OLLAMA_NUM_PARALLEL` of 1, 2 and 4 gave 0.49, 0.49 and 0.47 batches a second. `num_batch` of 1024, 2048 and 8192 gave no gain. So the tier keeps one slot and sets neither.
- For the same input, a vector from a P6000 has a cosine of 0.99945 to a vector from a Tesla V100, and 0.99951 to one from an RTX 3090 (#2396 saw 0.78 to 0.92 from a different KV cache). Vectors from the two P6000 are the same.
- `ollama serve --help` lists `OLLAMA_NOPRUNE`.
- An idle Tesla V100 embeds the same batch in 1.0 s. Two P6000 are about equal to it in throughput, and they gain by having no chat model to wait for.

## Existing Tool Considered

Helm can compare the values in a template, and Argo CD reads a chart. Kustomize has no comparison, so a component for each value is a fixed list and not a threshold.

The build costs about 60,000 tokens and 2 h now, and about 5,000 tokens a year to keep. A chart means rewriting the 1,340 lines of the profiles, the Services and the generated LiteLLM ConfigMap, moving the `llm` Application to a chart source, and about 20 tests that read those files: about 400,000 tokens and 1 day, for one tier that follows the thresholds. `devops ai gateway render` is already the render step of this configuration. Reconsider a chart when a second tier gets a template.

The change deletes the hand-written DaemonSet and Service of `ollama-48gib-slow`, and no other internal code.
