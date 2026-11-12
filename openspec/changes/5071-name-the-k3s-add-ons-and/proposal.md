# Proposal: #5071 name the k3s add-ons and the real spend-log cleanup time

## Why

Closes #5071. Three statements in `k8s/README.md` and the gateway files are wrong or incomplete:

- The GitOps section names CoreDNS as the only object that k3s, not git, holds. The drift rule above it then covers the other k3s add-ons, and a reader can delete metrics-server.
- The CoreDNS paragraph has a sentence of 33 words, and it names #4993 as future work. That text becomes wrong when #4993 merges.
- The gateway config comment, the Spend logs item and a gate-check docstring say that the spend-log cleanup runs once a day. LiteLLM starts it 24 hours after each start of the gateway process.

## What Changes

- `k8s/README.md`, GitOps: the drift rule names the k3s packaged add-ons as its exception. A new paragraph says how to list them, gives the add-ons of k3s v1.37 and the annotation that marks their objects. The CoreDNS paragraph becomes one case of it. Its long sentence becomes two sentences, and it keeps the fact that no alert reads the CoreDNS memory without the reference to #4993.
- `k8s/README.md`, Spend logs; `k8s/llm/gateway/config.yaml`, the comment above `maximum_spend_logs_retention_period`; and the docstring of `check_the_gateway_keeps_its_spend_logs_for_30_days`: the cleanup runs 24 hours after each start of the gateway process, then each 24 hours. A restart before 24 hours delays the run.
- The change edits documents and comments only. No value, test assertion or manifest field changes, so the change has no spec delta (`skip_specs: true`). The requirement "The gateway keeps its spend logs for 30 days" of `llm-gateway-database` names the default interval of `1d`, and that stays correct.
- The comment change gives ConfigMap `llm-gateway-config-<hash>` a new hash. After the merge Argo CD rolls the gateway once, with no downtime (`maxSurge` 1, `maxUnavailable` 0).

The change fits one pull request.

## Capabilities

None. No requirement in `openspec/specs/` holds the changed sentences.

## Impact

- A reader who applies the drift rule keeps the k3s add-ons.
- The documents state the real time of the spend-log cleanup.

## Feasibility

- `kubectl -n kube-system get addon` (server v1.37.2+k3s1, read only) lists 12 add-ons: `coredns`, `ccm`, `rolebindings`, `runtimes`, `gateway-api-crd`, and `aggregated-metrics-reader`, `auth-delegator`, `auth-reader`, `metrics-apiservice`, `metrics-server-deployment`, `metrics-server-service`, `resource-reader` of metrics-server.
- Deployments `metrics-server` and `coredns` have the annotation `objectset.rio.cattle.io/owner-gvk: k3s.cattle.io/v1, Kind=Addon`, and `objectset.rio.cattle.io/owner-name` names their add-on. Each RuntimeClass, `nvidia` included, has the owner `runtimes`. APIService `v1beta1.metrics.k8s.io` points to `kube-system/metrics-server`. `k8s/llm/profiles/ollama-profiles.yaml` sets `runtimeClassName: nvidia`.
- The k3s document of packaged components (https://docs.k3s.io/installation/packaged-components) says that k3s deploys each packaged component as an AddOn from the manifests folder, and writes the files again when it starts.
- LiteLLM v1.103.10 (`ghcr.io/berriai/litellm:v1.103.10` in `k8s/llm/gateway/deployment.yaml`), `litellm/proxy/proxy_server.py` lines 10347 to 10388: with no `maximum_spend_logs_cleanup_cron`, it adds `spend_log_cleanup_job` with an `"interval"` trigger of `maximum_spend_logs_retention_interval` (default `1d`) plus 0 to 60 seconds. `litellm/proxy/common_utils/scheduled_job_stagger.py` line 4: "APScheduler anchors an `interval` job at `now + interval`". The stagger only adds an offset.
- `litellm/constants.py` lines 1736 to 1742: one run deletes up to 500 batches (`SPEND_LOG_RUN_LOOPS`) of 1,000 rows (`SPEND_LOG_CLEANUP_BATCH_SIZE`) in 300 seconds.
- Prometheus, 14.5 days to 2026-11-12: `kube_pod_start_time` shows 23 gateway pods, and 18 of them lived less than 24 hours. Thus about 8 cleanup runs occurred, and the longest time between two runs was about 73 hours.

## Existing Tool Considered

The change uses the k3s add-on list (`kubectl -n kube-system get addon`) and the LiteLLM scheduler as they are, and builds nothing. It deletes no internal code.
