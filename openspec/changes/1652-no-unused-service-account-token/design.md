# Design

## Context

Kubernetes mounts a token of the pod's ServiceAccount into each pod, unless the pod spec or the ServiceAccount sets `automountServiceAccountToken: false`. The pod field wins over the ServiceAccount field. The workloads of the cluster come from two sources: the manifests under `k8s/`, and the charts that the Argo CD Applications in `k8s/argocd/apps/` install with a values file from the tree. Argo CD tracks `main` with automated prune and self-heal.

A chart binds its own Roles and ClusterRoles, so a binding of a chart pod is not in the tree. `tests/test_k8s_local_path_placement.py` (#1634) met the same problem for claims with a table of the pods of each chart.

## Goals / Non-Goals

**Goals:**

- No pod that does not call the API mounts a token.
- A test fails when a pod mounts a token with no binding and no named exception, when an Application installs a chart that the test does not know, and when an exception is stale.

**Non-Goals:**

- The pods that Argo Workflows makes from a WorkflowTemplate. Their `wait` container reports the results through the API, with the executor ServiceAccount.
- The pods of the cluster that the tree does not deploy: the k3s add-ons (CoreDNS, metrics-server, local-path-provisioner) and the NVIDIA device plugin.
- Fewer rights for a pod that calls the API.

## Decisions

- **Decision: one rule for manifest pods and chart pods.**
  *Choice:* a pod passes when its token is off (on the pod, or on its ServiceAccount) and no volume holds a token, when a role binds its ServiceAccount, or when it is in `CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS`. For a manifest pod, the test finds the RoleBindings and ClusterRoleBindings under `k8s/`. For a chart pod, the table of the test names the Role or ClusterRole with rules that the chart binds to it, as `helm template` showed.
  *Rejected alternative:* a named exception for each chart pod that calls the API.
  *Evidence for rejection:* 18 chart pods call the API (Argo CD, Argo Workflows, Image Updater, Grafana, k8s-monitoring, the Prometheus server, Pyroscope and Traefik). A manifest pod with a binding needs no exception, and a chart pod with a binding is the same case. The exceptions then hold only the pods that keep a token they do not need, or whose binding the tree cannot show.

- **Decision: a table of chart pods in the test, not a chart render.**
  *Choice:* `CHART_TOKENS` names, for each chart that an Application installs, the pods that the chart makes with the values in the tree, the value that turns the token off (with the chart's default), and the role of each pod that calls the API. The k8s-monitoring collectors come from `collectors` in the values. A chart that the table does not name fails the test. Each entry also names the chart version that `helm template` read, and the test fails when an Application pins another version. A chart release can move the value that sets the pod field, as Loki 20.0.2 did (#1632).
  *Rejected alternative:* `helm template` of each chart in the test.
  *Evidence for rejection:* a test starts no program and reaches no network (docs/TESTING.md), and a render needs each chart from the network or a vendored copy. The same evidence rejected a render in #1634.
  *Known limit:* a values change that turns on a chart pod that the table does not name, such as Argo CD's dex, passes until the table names it. The table names the optional pods that the values in the tree turn off (dex, notifications and the commit server of argo-cd, the Loki canary and gateway), so that a change of their switch fails the test.

- **Decision: the tree uses only the inputs that the readers see.**
  *Choice:* the readers of `tests/support/k8s_tree.py` read the files under `k8s/` and the values files of the Applications. Argo CD also takes chart values from `helm.values`, `helm.valuesObject` and `helm.parameters`, and Kustomize changes objects with patches. A test fails when an Application source has an option that the readers do not read, or when a kustomization has a key that changes objects or patches an object that a check reads. The test also keeps the claim check of `tests/test_k8s_local_path_placement.py` correct, because that check uses the same readers.
  *Rejected alternative:* readers that render each Application path with `kubectl kustomize`, which the test floor admits.
  *Evidence for rejection:* today no Application gives inline values, and the one patch of the tree deletes an Ingress, so the files show what Argo CD applies. A render shows only the files that a kustomization lists, so it loses the file of each object, which the keys of the exceptions use, and it changes the claim check too. A render also cannot apply inline chart values without the chart.

- **Decision: turn off the token of each chart pod that does not call the API.**
  *Choice:* Loki, Tempo, the OpenTelemetry collector, Alertmanager, the Argo CD repo server and Redis, and Gitea. The issue named only Loki among the charts. For Loki, the issue named `serviceAccount.automountServiceAccountToken`. Loki chart 20.0.2 (#1632) sets the pod field from `defaults.automountServiceAccountToken`, and the pod field wins over the ServiceAccount field. Thus the values set both keys to `false`. `helm template` showed the other six with no binding, or with a Role that has no rules.
  *Rejected alternative:* named exceptions for the six, and a later issue.
  *Evidence for rejection:* an exception for a pod that does not need its token keeps the defect of the issue. Each fix is one value that the chart offers.

- **Decision: Gitea gets the chart's own ServiceAccount.**
  *Choice:* `serviceAccount.create: true` and `serviceAccount.automountServiceAccountToken: false` in `k8s/gitea/values.yaml`. The pod then uses the ServiceAccount `gitea`, which has no token.
  *Rejected alternative:* a token setting on the pod.
  *Evidence for rejection:* gitea 12.7.0 sets no `automountServiceAccountToken` on the pod. It sets the field only on the ServiceAccount that it makes.

- **Decision: Qdrant stays an exception.**
  *Choice:* `k8s/llm/values-qdrant.yaml:qdrant` in `CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS`. qdrant/qdrant-helm#506 asks for `serviceAccount.automountServiceAccountToken`, so the repository files no second request. The entry goes when a chart release adds the value.
  *Rejected alternative:* a post-render step (Kustomize or an Argo CD plugin) that adds the field.
  *Evidence for rejection:* the issue rejects a home-grown post-render step for this one field.
  *Rejected alternative:* qdrant 1.20.0 with `serviceAccount.create: false` and a ServiceAccount from the tree.
  *Evidence for rejection:* the bump also changes the Qdrant server version, which is a change of its own.

- **Decision: the CoreDNS patch is an exception.**
  *Choice:* `k8s/coredns/deployment-patch.yaml:Deployment/coredns` in the exceptions. k3s makes the CoreDNS Deployment, its ServiceAccount `coredns` and the ClusterRoleBinding `system:coredns`, and the file patches only the resources.
  *Rejected alternative:* leave patch files out of the test.
  *Evidence for rejection:* the test cannot tell a patch from a full Deployment, and a skip rule for patches would also skip a real workload.

- **Decision: the invariant goes into `tests/invariants/test_k8s_manifests.py`.**
  *Choice:* docs/TESTING.md puts each invariant test into the file of its subject, and the subject is the manifests under `k8s/`. The issue names `tests/test_k8s_devops_runtime.py`, which tests only the `devops` namespace.
  *Choice:* the readers of the tree go into `tests/support/k8s_tree.py`, and `tests/test_k8s_local_path_placement.py` uses them. A test imports only from `tests/support/`.

- **Decision: no scanner.**
  *Choice:* the test. See the proposal, Existing Tool Considered.
  *Rejected alternative:* Trivy's misconfiguration scan.
  *Evidence for rejection:* Trivy 0.75.0 gave no token finding on a Deployment that leaves the field unset or sets it to `true`.

## Risks / Trade-offs

- A pod that needs its token and loses it fails at start or on its first API request. Mitigation: each pod that loses its token has no binding, or a Role with no rules, and `kubectl auth can-i --list` shows only discovery for each of its ServiceAccounts. Upstream Argo CD ships its repo server with no token.
- Argo CD syncs its own Application. A failure of the repo server would stop each sync. Mitigation: the upstream install manifest of the same Argo CD version sets the field to `false` on the repo server.
- Gitea moves from the ServiceAccount `default` to the ServiceAccount `gitea`. No Role binds either of them.
