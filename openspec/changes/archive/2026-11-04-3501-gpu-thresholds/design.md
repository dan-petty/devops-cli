## Context

Argo CD syncs `k8s/llm` from `main` with Kustomize, and the manifests are static files. `devops ai gateway render` already aligns the gateway config with the profiles. No Ollama pod claims `nvidia.com/gpu`, so each pod sees every GPU of its node. Each tier is one DaemonSet, which the deploy check and many tests read from `ollama-profiles.yaml`.

## Decisions

### The thresholds are a tracked file

The values are in `k8s/llm/profiles/gpu-thresholds.yaml`, and not in settings. `config.yaml` is local to one workstation, and Argo CD tracks `main`. A setting would let one render flip the manifests of another person, with no record of the value in git.

### A rendered region in each manifest

`tier-templates/` holds one DaemonSet per tier that follows the thresholds, written as a chat tier. Kustomize does not read it. The render writes between two marker lines, so the rest of each file keeps its comments, and every reader of the manifests works unchanged. The output has no comments, and the tracked-manifest test holds the regions equal to the output.

Rejected: rewriting the DaemonSets in place. A lower threshold could not bring back the settings that a higher one removed, and comments do not survive a round trip of the transform.

### One DaemonSet per GPU, with a device-plugin claim

Each instance is a DaemonSet with `nvidia.com/gpu: 1`, so the device plugin picks the GPU. A later instance requires a matching `nvidia.com/gpu.count`, with the operator `In`, the one operator of the placement check.

Rejected: `NVIDIA_VISIBLE_DEVICES` with fixed indexes in two containers of one pod. It gives the scheduler no record of the claim, and one pod would restart both instances. Also rejected: a Deployment with replicas. Its count is per cluster, not per node, and the placement check reads DaemonSets.

### A gateway deployment per instance

Each instance has a Service and a LiteLLM deployment. Through one Service, kube-proxy picks a pod per connection, so two parallel batches can share one GPU, and a batch that shares one GPU waits for the other (at 4 streams, the longest wait was 8.0 s on one instance and 4.2 s on two). With one deployment each, `simple-shuffle` spreads the batches, a cooldown takes out one instance, and the gateway metrics show each GPU.

### The name says what the tier is

A rendered tier is `ollama-<VRAM of one instance>gib-<embed or speed tier>`, with `-gpu<n>` for each instance. Its labels follow the name, with a speed tier of `embed`. The selectors of `ollama-slow`, `ollama-24gib` and `ollama-24gib-slow` ask for `slow`, so a chat client of those Services does not reach an embedding-only tier. Ollama has no setting that limits a server to embedding models, so routes and selectors are the limit.

### The render refuses and does not move

A generation deployment on an embedding-only tier fails the render and names each group. Which tier serves a group instead is a routing decision. A threshold newer than the newest architecture of the templates also fails: tiers such as `ollama-64gib` accept any architecture and have no template, so they could not follow it, and a silent no-op would mislead.

### devops-background moves to ollama-64gib-standard

The group needs a chat tier. `ollama-64gib-standard` is the slowest chat tier and already serves `qwen3.8:27b`. Background work now waits with the interactive and review calls of that tier, and those calls wait for it. Rejected: `ollama-48gib-fast`, which holds `devops-coder` (#3485).

### Embedding-only settings

`OLLAMA_CONTEXT_LENGTH` is `CONST_RAG_MAX_CHUNK_TOKENS`, so a call with no `num_ctx` does not load the 32,768-token default. `OLLAMA_MAX_LOADED_MODELS` is 1, and the template keeps `OLLAMA_KEEP_ALIVE: -1`, so no batch takes the 1.8 s of a cold load. Requests are 2 CPU and 2 GiB, and the limit is 4 GiB, against a measured peak of 890 MiB. `OLLAMA_NOPRUNE` is on for every per-GPU instance, because the instances of a node share one model directory, and a start that prunes removes each blob that no manifest names yet. `OLLAMA_NUM_PARALLEL` stays 1: 2 and 4 gave no gain.

## Risks

- Peak embedding throughput: two P6000 give 0.99 batches a second, about equal to one idle Tesla V100. Order 1 no longer includes the faster GPUs, except as a fallback. The gain is in the longest waits and in the chat tiers.
- Only the tiers in `tier-templates/` follow the thresholds. A Pascal node with a total VRAM of another tier runs that tier as it is written.
