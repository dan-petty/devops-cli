# Task 463: One Gateway Deployment per Ollama Node

**Issue**: [#463](https://github.com/dan-petty/devops-cli/issues/463)
**PR**: [#464](https://github.com/dan-petty/devops-cli/pull/464)
**Status**: In Review
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/k8s`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

The gateway reached Ollama through the `ollama` Service. kube-proxy balances per TCP connection
and LiteLLM keeps its connections open, so all gateway traffic to Ollama went to whichever pod
the first connections landed on. In a full review, one Ollama node served 15 requests and the
other served 0. Because every Ollama node sat behind one gateway deployment, LiteLLM could not
match load to each node's single request slot (`OLLAMA_NUM_PARALLEL=1`), and it could not cool
down a failing node without cooling down all of them.

The gateway's health report was also wrong. `devops-embedding` was reported unhealthy because it
was probed with a generate call, and the `ollama/*` wildcard was probed with a placeholder model.

### Key Deliverables Completed:

- [x] **Ollama StatefulSet** (`k8s/llm/ollama.yaml`, formerly `ollama-daemonset.yaml`): pods
  get stable DNS names through the headless `ollama-nodes` Service. Required pod anti-affinity
  keeps one pod per GPU node, and `podManagementPolicy: Parallel` stops an offline node from
  blocking the others. Architecture affinity, `hostPort`, node-local `hostPath` models and the
  `ollama` NodePort Service are unchanged.
- [x] **Per-Pod Gateway Deployments**: `devops-chat`, `devops-embedding`, the Ollama tier of
  `devops-review` and the `ollama/*` pass-through each list every pod. Review entries take
  `max_parallel_requests: 1`, matching `OLLAMA_NUM_PARALLEL`. `devops-chat` moves to
  `ollama_chat/`, the same chat endpoint the review tier uses.
- [x] **Health Checks**: `mode: embedding` for embedding deployments, and a real
  `health_check_model` for the wildcard.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_k8s_llm_gateway.py`: per-pod deployments track the StatefulSet's replica count
    and `OLLAMA_NUM_PARALLEL`; the headless Service, anti-affinity and shared Service; health
    check modes; review windows per pod.
  - `tests/test_k8s.py`, `tests/test_k8s_squid.py`: probes, storage and proxy settings on the
    StatefulSet.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Rollout

The DaemonSet holds host port 11434, so it must be deleted before the StatefulSet can start:

```bash
kubectl -n llm delete daemonset ollama
kubectl apply -f k8s/llm/ollama.yaml
kubectl -n llm rollout status statefulset/ollama
kubectl apply -f k8s/llm/gateway/configmap.yaml
kubectl -n llm rollout restart deployment/llm-gateway
```

Models stay on each node's `hostPath`, so nothing is downloaded again.

## 3. Verification on a Live Cluster

After the rollout, one pod ran on each Ollama node, and both still had their models. Gateway
`/health` reported all 12 deployments healthy and none unhealthy. Before, `devops-embedding` and
the wildcard were reported unhealthy. Of eight concurrent `devops-chat` requests, one node served
five and the other three. Before the change, a full review sent 15 requests to one node and 0 to
the other.
