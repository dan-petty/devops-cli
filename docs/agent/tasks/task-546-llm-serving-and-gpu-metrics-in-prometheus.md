# Task 546: LLM Serving and GPU Metrics in Prometheus

**Issue**: [#546](https://github.com/dan-petty/devops-cli/issues/546)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

Prometheus scraped no `vllm:*`, `litellm_*` or GPU metric, so each backend's load, queue and
latency could not be seen or kept; #545's imbalance was found by exec-ing `nvidia-smi` in each
pod. The shipped `llm-stack.json` dashboard queried `http_requests_total`, which nothing in the
stack exposes, so it was empty.

### Key Deliverables Completed:

- [x] **vLLM servers**: `prometheus.additionalServiceMonitors` in
  `k8s/monitoring/prometheus-values.yaml` scrapes both servers' `/metrics` every 15s.
  - The chart creates the monitor itself, so it never waits on the ServiceMonitor CRD.
  - `job` is the service name.
  - Their network policies admit the monitoring namespace on 8000.
- [x] **Gateway**: LiteLLM's Prometheus callback is on (`litellm_settings.callbacks`); it is
  open source in v1.102.1. A monitor scrapes `/metrics/`. Per deployment, this gives:
  - requests and failures;
  - call latency, whose rate is the mean number of calls in flight.

  The Ollama nodes export no metrics of their own, so this is how their load is seen.
- [x] **GPUs**: NVIDIA's DCGM exporter chart (`dcgm-exporter-values.yaml`, 4.6.1-4.8.4) joins
  the infra stack.
  - It runs on nodes labelled `nvidia.com/gpu.present`, with the `nvidia` runtime class and the
    GPU taint tolerated.
  - It has no added capability: profiling fields need datacenter GPUs and `SYS_ADMIN`, so they
    are left out.

  Prometheus now selects every ServiceMonitor, so the chart's own monitor is used.
- [x] **Network**: Prometheus may reach the `llm` namespace on 8000 and 4000.
- [x] **`llm-stack.json` rebuilt**, with the Qdrant panels kept:
  - calls in flight, requests and failures per deployment;
  - vLLM requests running and waiting;
  - gateway latency p95 per deployment;
  - vLLM time to first token and queue time;
  - KV cache use and token throughput;
  - GPU utilisation, memory, power and temperature.

  Metric names were checked against the live vLLM v0.30.0 `/metrics`, LiteLLM's exposition
  (`prometheus_client` appends `_total` to counters) and DCGM's default counters.
- [x] **`devops ai gateway load --window 1h`**, moved here from #557. It reports each
  backend's:
  - requests, failures and mean calls in flight;
  - for vLLM servers, the share of the window with a request running, and the mean and peak
    queue.

  It also reports each GPU's mean utilisation and peak memory. Gateway and vLLM figures for one
  backend are joined on its host name. It can print a table or JSON.
- [x] **Automated Tests & Quality Gates** (`tests/test_llm_pool_metrics.py`):
  - dashboard metric names;
  - each monitor matches its services' labels and ports;
  - network policies;
  - the gateway callback;
  - DCGM scheduling and privileges;
  - joining gateway and vLLM views of a backend;
  - windows;
  - the command's table, JSON, empty and error cases.

  100% passing status across Gated CI validation suite (`uv run devops ci`).

### Not verified in the cluster

The manifests were checked in tests, not applied. After merge:
1. Upgrade kube-prometheus-stack and the gateway, and install the DCGM exporter (`devops k8s up`
   for the infra stack; `kubectl apply -k k8s/llm`).
2. Apply the network policies.
3. Run `devops ai gateway load --window 15m` during a review.
