# Proposal

## Why

Issue #1652: most workloads that the repository deploys mount a Kubernetes API token that they never use. Only the `devops` namespace and the agents' ServiceAccount turn the token off. An attacker in one of these containers gets a valid cluster identity. The internet-facing `cloudflared` pods are among them, and their NetworkPolicy allows the API server on port 6443. Today each of these tokens grants only discovery. A later RoleBinding to the `default` ServiceAccount of a namespace would reach every pod of that namespace with no warning.

## What Changes

- Add a test to `tests/invariants/test_k8s_manifests.py`. Each pod that a manifest under `k8s/` declares, or that a chart of an Argo CD Application makes, mounts no ServiceAccount token, or the pod's ServiceAccount is bound to a role that it uses, or the pod is a named exception with a reason. The test fails on a chart or a chart version that it does not know, and on a stale exception. It also fails when an Application gives a chart values that are not in its values files, or when a kustomization patches an object that the test reads, because the test reads the files only.
- Add `automountServiceAccountToken: false` to the pod templates of `cloudflared`, `gpu-feature-discovery`, `llm-gateway`, `portkey`, `valkey`, `valkey-runs` and the nine Ollama tiers.
- Turn the token off in the chart values of the pods that do not call the API: Loki (`defaults.automountServiceAccountToken` for the pods and `serviceAccount.automountServiceAccountToken` for the ServiceAccount), Tempo and the OpenTelemetry collector (the same key), Alertmanager (`alertmanager.automountServiceAccountToken`), the Argo CD repo server and Redis (`repoServer.` and `redis.automountServiceAccountToken`), and Gitea (`serviceAccount.create: true`, whose ServiceAccount has no token).
- Add the table `_TOKEN_EXCEPTIONS` to the test, with a reason for each entry: Qdrant, whose chart has no value for the token (qdrant/qdrant-helm#506 asks for it), and the CoreDNS patch, whose Deployment k3s owns. The issue asks for the table in `src/devops_cli/config/constants.py`. CONTRIBUTING.md now puts a table that one module reads beside that module, so the table goes into the test.
- Move `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` from `src/devops_cli/config/constants.py` to `_CONTROL_PLANE_CLAIM_EXEMPTIONS` in `tests/test_k8s_local_path_placement.py`, its one reader, which the change edits.
- Move the readers of the `k8s/` tree that `tests/test_k8s_local_path_placement.py` holds into `tests/support/k8s_tree.py`, so that the two tests share them.
- Document the rule and the exceptions in `k8s/README.md`, Service Account Tokens.
- The manifests and the chart values are observable behavior, so the change has a spec delta: the new capability `service-account-tokens`. The requirement of `local-path-volume-placement` names its table of exemptions, so that capability changes too.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `service-account-tokens`: which pods of the cluster mount a Kubernetes API token.

### Modified Capabilities

- `local-path-volume-placement`: the requirement names the table of exemptions in the test, not a constant in `src/devops_cli/config/constants.py`.

## Impact

- `k8s/cloudflared/deployment.yaml`, `k8s/gpu-feature-discovery/daemonset.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/llm/portkey/deployment.yaml`, `k8s/llm/valkey.yaml`, `k8s/llm/valkey-runs.yaml`, `k8s/llm/profiles/ollama-profiles.yaml`.
- `k8s/logging/loki-values.yaml` (only the `defaults` and `serviceAccount` keys), `k8s/otel/tempo-values.yaml`, `k8s/otel/values.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/argocd/values.yaml`, `k8s/gitea/values.yaml`.
- `src/devops_cli/config/constants.py`: the table `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` goes.
- `tests/invariants/test_k8s_manifests.py`, `tests/support/k8s_tree.py`, `tests/test_k8s_local_path_placement.py`.
- `k8s/README.md`.
- The live cluster after the merge: Argo CD tracks `main` with prune and self-heal, so it syncs each changed Application and restarts the pods whose template changes. Argo CD syncs its own Application too, which restarts its repo server and Redis.

## Feasibility

Checked on 2026-10-28 against the homelab cluster (k3s, Argo CD v3.5.3) and the pinned charts:

- Live pods. `kubectl get pods -A -o json` shows a `kube-api-access-*` volume on `cloudflared` (2), `gpu-feature-discovery` (4), `llm-gateway`, `portkey`, `valkey`, `valkey-runs`, four Ollama tiers, `qdrant-0`, `loki-0`, `tempo-0`, `prometheus-alertmanager-0`, the OpenTelemetry collector, `argocd-redis`, `argocd-repo-server` and `gitea`, and on each pod that calls the API. The `registry` workload of the issue is gone (#1630). `loki-canary` is off in `loki-values.yaml`.
- Rights. `kubectl auth can-i --list --as=system:serviceaccount:<namespace>:<name>` for `cloudflared:default`, `llm:default`, `default:default`, `llm:qdrant`, `logging:loki`, `otel:tempo`, `otel:otel-collector-opentelemetry-collector`, `monitoring:prometheus-alertmanager`, `argocd:default`, `argocd:argocd-repo-server` and `gitea:default` shows only the self reviews and the discovery paths.
- Charts. `helm template` of each chart at the version its Application pins, with the values in the tree, gives the pods, their ServiceAccounts, and the Roles and ClusterRoles bound to them. The Loki ClusterRole and the Argo CD repo server Role have no rules. The collector, Tempo, Alertmanager, Argo CD Redis, Gitea and Qdrant have no binding.
- Chart keys. `helm show values` and the templates: tempo 3.1.0 and opentelemetry-collector 0.175.0 set the pod field from `serviceAccount.automountServiceAccountToken`. #1632 moved Loki to grafana-community/loki 20.0.2. That chart sets the pod field of each Loki pod from `<component>.automountServiceAccountToken`, or else from `defaults.automountServiceAccountToken`, which is `true` by default (`templates/_pod.tpl:56-60`). `serviceAccount.automountServiceAccountToken` sets only the field of the ServiceAccount (`templates/_serviceaccount.tpl:26`), and the pod field wins. `helm template` with only `serviceAccount.automountServiceAccountToken: false` gives the StatefulSet `loki` the pod field `true`, and the live `loki-0` (chart label `loki-20.0.2`) has the field `true` and a token. With `defaults.automountServiceAccountToken: false`, the StatefulSet has the field `false`. The canary and the gateway read `lokiCanary.` and `gateway.automountServiceAccountToken`, which are `false` by default. The alertmanager 2.0.1 subchart of prometheus 29.35.0 uses `alertmanager.automountServiceAccountToken`. argo-cd 10.9.6 has `<component>.automountServiceAccountToken` for each component. gitea 12.7.0 uses the `default` ServiceAccount unless `serviceAccount.create` is true, and its own ServiceAccount has `automountServiceAccountToken: false` by default. qdrant 1.19.1 offers only `serviceAccount.annotations`, and 1.20.0 adds only `serviceAccount.create` and `name`.
- Upstream. The Argo CD v3.5.3 `manifests/install.yaml` sets `automountServiceAccountToken: false` on the repo server. The chart's Redis pod runs only Valkey and its exporter. A PreSync hook Job writes the Redis password Secret.
- No API use. gpu-feature-discovery v0.16.2 writes its labels to the host file `features.d`, with no `USE_NODE_FEATURE_API`. The collector configures no `k8sattributes` processor and no Kubernetes preset.
- Helm hooks. The Argo CD v3.5.3 Helm guide maps `pre-install`, `pre-upgrade`, `post-install`, `post-upgrade`, `pre-delete` and `post-delete`, and does not support the test hooks. Thus Argo CD runs the hook Jobs of argo-cd and k8s-monitoring, and never the test pods of grafana and qdrant.

## Existing Tool Considered

- Trivy 0.75.0, the pinned misconfiguration scanner (#2464). `trivy config` on `k8s/cloudflared` and on a Deployment with `automountServiceAccountToken: true` gives no token finding. Thus its check does not cover a pod that leaves the field unset.
- kube-linter 0.8.3 has no check for the token. Its `default-service-account` check finds the `default` ServiceAccount, not the token.
- Kubescape control C-0034 finds a mounted token, but `tools.lock` does not pin Kubescape, and no scanner adapter exists for it. It also scans only manifests, not the charts of the Applications without a render.
- The build: one test with a table of chart pods, in the pattern of `tests/test_k8s_local_path_placement.py`, and two named exceptions. Cost: about 150 thousand tokens to build, about 5 thousand tokens for each later chart change, and about 2 hours elapsed.

The change deletes the private readers of `tests/test_k8s_local_path_placement.py` (`_get`, `_documents`, `_chart_values`, `_value_files`, `_manifests`, `_pod_spec` and `POD_SPEC_PATHS`), which `tests/support/k8s_tree.py` replaces.
