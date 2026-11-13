# Proposal: #5301

## Why

Three settings of the LiteLLM gateway and its database use a Kubernetes or CloudNativePG default, and each default cuts open model calls or stops the start of the gateway (#5301).

- The gateway pod sets no `terminationGracePeriodSeconds`, so the kubelet kills the old pod 30 s after SIGTERM. Uvicorn waits for each open call, but a call can run for minutes. In 7 days, 3 of 10 stops of the gateway cut open calls, and the roadmap Service skipped 2 refine calls.
- The gateway database Cluster `llm-gateway-db` uses the default `smartShutdownTimeout` of 180 s. On 2026-11-12, the idle sessions of the old gateway pod kept the smart shutdown open for 3 minutes. The database refused new connections, and the new gateway pod stopped 4 times after its migration check.
- The gateway probes set no `timeoutSeconds`, so each probe waits 1 s. One slow request holds the one uvicorn worker for some seconds, and 28 probes failed in 7 days.

## What Changes

- `k8s/llm/gateway/deployment.yaml`: the pod sets `terminationGracePeriodSeconds: 600`. The startup, liveness and readiness probes set `timeoutSeconds: 5`.
- `k8s/llm/gateway-db.yaml`: the Cluster sets `smartShutdownTimeout: 15`.
- `allow_requests_on_db_unavailable` stays unset in `k8s/llm/gateway/config.yaml`.
- Three checks of the `k8s` row (`tests/gate/k8s_checks/gateway_database.py`) hold the three values.
- `k8s/README.md` tells how the gateway and its database stop, why the two images change in different pull requests, and that a person reads the spend-log rows with the paginated `/spend/logs/v2`.
- A manifest changes the behavior of the service, so the change has a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-gateway-database`: three added requirements for the grace period of the gateway pod, the smart shutdown of the database and the probe timeout of the gateway.

## Impact

- Render: `kubectl kustomize k8s/llm` (Argo CD Application `llm`) and `kubectl kustomize k8s/llm/gateway` (deploy-stack) add only `terminationGracePeriodSeconds: 600` to the pod template of `llm-gateway`, `timeoutSeconds: 5` to its three probes, and, in `k8s/llm`, `smartShutdownTimeout: 15` to the Cluster `llm-gateway-db`. The name of the gateway ConfigMap does not change.
- At the merge, the pod template changes, so the gateway rolls one time: the new pod starts first, and Kubernetes stops the old pod when the new pod is ready. The old pod keeps the grace period of its own spec, 30 s, so this one rollout can still cut a call that is open for more than 30 s. The next rollouts use 600 s.
- The database does not restart. CloudNativePG 1.30.1 does not put `smartShutdownTimeout` in the pod spec or in the environment hash of the instance, and the instance manager reads the value from the Cluster at each stop.
- A node drain can wait up to 600 s for the gateway pod.

## Feasibility

- The premise was checked against origin/main `fbb7c7284` on 2026-11-13. `k8s/llm/gateway/deployment.yaml` sets no `terminationGracePeriodSeconds`, no `preStop` and no `timeoutSeconds` on the three probes. It sets no `strategy`, so the default rolling update applies (1 replica: `maxSurge` 1, `maxUnavailable` 0). `k8s/llm/gateway-db.yaml` sets no `smartShutdownTimeout`. `k8s/llm/gateway/config.yaml` sets the router `timeout` to 1500 and the `devops-background` timeout to 1100.
- The live objects agree. `kubectl -n llm get cluster llm-gateway-db` shows `smartShutdownTimeout` 180, `stopDelay` 1800 and `primaryUpdateMethod` restart. The operator image is `cloudnative-pg:1.30.1`. `kubectl diff` of the rendered objects (a server-side dry run, with no apply) shows only `terminationGracePeriodSeconds` 30 to 600, `timeoutSeconds` 1 to 5 on the three probes, and `smartShutdownTimeout` 180 to 15. The admission webhook of CloudNativePG accepts the value.
- LiteLLM v1.103.11 `litellm/proxy/proxy_cli.py:267-292` builds the uvicorn arguments with no `timeout_graceful_shutdown`, so uvicorn waits for open calls until the kubelet kills it.
- CloudNativePG v1.30.1 source: `pkg/specs/pods.go:536` sets the `terminationGracePeriodSeconds` of the instance pod from `stopDelay` only, and `CreatePodEnvConfig` (`pods.go:126-181`) holds no shutdown value. `pkg/management/postgres/instance.go:637-689` (`TryShuttingDownSmartFast`) reads `smartShutdownTimeout` from the cached Cluster at each stop, and `internal/management/controller/instance_controller.go:164` refreshes that cache at each reconcile. Thus a change of the value restarts no instance. `docs/src/instance_manager.md` gives the defaults 180 s and 1800 s.
- The incident evidence is in the issue body: the Loki logs of the gateway, the database and the roadmap Service, and the kubelet events of the probes.

## Existing Tool Considered

- Kubernetes (`terminationGracePeriodSeconds`, `timeoutSeconds`) and CloudNativePG (`smartShutdownTimeout`) cover the need with fields that they already have. The change adds no tool and no code, and deletes no code.
