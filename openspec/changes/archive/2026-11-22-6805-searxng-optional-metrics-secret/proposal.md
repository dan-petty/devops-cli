# Proposal: #6805

## Why
Closes #6805. The init container `render-settings` of Deployment `searxng` reads key `password` of Secret `devops/searxng-metrics-auth` through a required reference. When that Secret is missing, the kubelet does not start the init container, so a new pod of SearXNG stays in `Init:CreateContainerConfigError`. Search needs no metrics: the Secret serves only the OpenMetrics endpoint `/metrics`, an optional feature. A missing Secret of an optional feature must not stop the main service (#5200).

## What Changes
- `k8s/devops/searxng/deployment.yaml`: the reference of `render-settings` to key `password` of Secret `searxng-metrics-auth` gets `optional: true`. When the variable is missing or empty, the script writes `''` in place of the placeholder `${SEARXNG_METRICS_PASSWORD}`, so `general.open_metrics` is empty and SearXNG turns `/metrics` off. It logs one line that names Secret `devops/searxng-metrics-auth` and exits 0. With the Secret, the script writes the password as before.
- `src/devops_cli/k8s/cluster_secrets.py`: entry `password` of row `devops/searxng-metrics-auth` is not required, and `OPTIONAL_FEATURE_SECRETS` names the row. A push with no keyring value and no live value skips the password with a warning, so `devops k8s deploy-stack --stack devops` does not stop on the metrics password.
- `tests/gate/k8s_checks/searxng_render.py`: a new check of the `k8s` row of `devops ci`. It runs the script of `render-settings` with `sh` against the volumes that the kubelet mounts, once with no Secret and once with a password that holds the special characters of `sed`.
- `k8s/README.md` says that the Secret is optional, in its rows and in its paragraph. `docs/CLUSTER.md` says what the pod and the scrape do while the Secret is missing. The comments of the ConfigMap and the Deployment say the same.
- The change alters the start of a pod and the behavior of a push, which a consumer observes, so it carries spec deltas.
- The change fits one pull request.

## Capabilities
- `searxng-service`: ADDED requirement "The pod starts without the metrics Secret".
- `searxng-service`: MODIFIED requirement "The pod renders its settings at start", which gets the scenario of a password that holds the special characters of `sed`.
- `stack-credential-sync`: MODIFIED requirement "The SearXNG metrics Secret row comes from the keyring", because the password entry is now optional.

## Impact
- A pod of SearXNG starts and searches while Secret `devops/searxng-metrics-auth` is missing. Its `/metrics` answers HTTP 404 `open metrics is disabled` until a person pushes the Secret and a new pod starts. A push that adds the password to an existing Secret restarts `deployment/searxng`; a push that creates the Secret restarts nothing, so the person restarts the Deployment.
- While the Secret is missing, Alloy makes no scrape target from ServiceMonitor `searxng`, so no `up` series and no `TargetDown` alert show the missing Secret. The ServiceMonitor stays.
- A push of stack `devops` with no `searxng_metrics_password` writes Secret `devops/searxng-metrics-auth` with key `username` only, and the pod keeps the endpoint off.

## Feasibility
- Live state on 2026-11-22 (read-only `kubectl`): `kubectl -n devops get secret searxng-metrics-auth` gives `NotFound`, and pod `searxng-ff6f7b56-885l6` is in `Init:CreateContainerConfigError` for 10 hours while pod `searxng-7bbfccd7d-zhkws` of the old ReplicaSet serves.
- Kubernetes: a `secretKeyRef` with `optional: true` lets the kubelet start the container when the Secret or its key is missing, and leaves the variable out. A required reference stops the start with `CreateContainerConfigError`, as the live pod shows.
- SearXNG source (`searx/webapp.py`, route `/metrics`): when `general.open_metrics` is empty, the endpoint answers `Response('open metrics is disabled', status=404)`.
- Alloy (`k8s-monitoring-alloy-metrics-0`, log of 2026-11-22): for ServiceMonitor `searxng` it logs `error generating scrapeconfig from serviceMonitor` with `err="secrets \"searxng-metrics-auth\" not found"` and makes no target. `TargetDown` in `k8s/monitoring/prometheus-values.yaml` is `up == 0`, so it needs a target and does not fire.
- `src/devops_cli/k8s/secret_push.py`: a required entry that no source holds is `missing`, a blocking state that stops the whole push; an entry that is not required is `skipped`.
- `docs/TESTING.md`: no pytest test reads a committed manifest or starts a system program, and a check of committed files is a row of `devops ci`. The checks of `tests/gate/k8s_checks/` render the manifests and some start programs, so the render check goes there.

## Existing Tool Considered
- Kubernetes `optional: true` on `secretKeyRef` is the standard way to start a pod without a Secret, and the change uses it. SearXNG turns the endpoint off with an empty `open_metrics`, and the change uses that setting.
- The check uses `sh`, `sed` and `kubectl kustomize`, which the `k8s` row already has. No open tool runs an init container script without a cluster.
- Build cost: about 5 lines of shell and a check of about 120 lines; about 40k tokens and 1 hour to build, and a low cost to keep.
- The change deletes no internal code.
