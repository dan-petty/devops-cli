# Proposal

## Why

Issue #1644: the charts that Argo CD renders still have the Helm release records of their last native deploy. Helm's default storage keeps each revision of a release as a Secret in the release's namespace, labelled `owner=helm` and `name=<release>`. Argo CD renders a chart with `helm template` and keeps no release. So `helm list` still shows these releases as `deployed`, and `helm rollback` or `helm uninstall` would roll back or delete objects that Argo CD owns, a chart's PersistentVolumeClaim included.

- AppProject `homelab` ignores every `sh.helm.release.v1.*` Secret as an orphan, so Argo CD never reports the leftover records.
- `k8s/README.md` has no step that retires the records. Its Recovery procedure runs `helm upgrade --install argocd`, which writes a new `argocd` record each time.
- The knowledge base page `it_domains/tools/helm.md` tells an agent to run `helm rollback prometheus 1 -n monitoring` and `helm uninstall prometheus -n monitoring`. Application `prometheus` renders release `prometheus` in namespace `monitoring`.

## What Changes

- New command `devops argo cd apps retire-helm-records`.
  - Without `--confirm` it only reads and prints the plan.
  - `--confirm` deletes the records of each qualifying release, by name.
  - `--dry-run` makes no request and lists the requests that a run makes.
- A release qualifies when two things hold:
  - An Application renders it: a source of the Application has a `chart`, and the release name is that source's `helm.releaseName`, or else the Application's name, in the Application's destination namespace.
  - Argo CD applied each top-level live object that carries the release's Helm annotations (`meta.helm.sh/release-name` and `meta.helm.sh/release-namespace`). That is, the object carries the Application's tracking id, or the field manager `argocd-controller` applied it.
- A record with an owner reference is never planned, because an operator owns it (the Alloy operator owns the `k8s-monitoring-alloy-*` records).
- The command reads the records and the objects through kubectl `jsonpath` output that holds only metadata, so no Secret data reaches the process.
- AppProject `homelab` no longer ignores `sh.helm.release.v1.*` Secrets, so Argo CD reports a record that is left over. Argo CD's orphan check skips the records that have an owner reference.
- `k8s/README.md` adds the retirement step to the end of "Bootstrap & Adoption" and of "Recovery".
- The knowledge base page `helm.md` says that a release that an Argo CD Application renders is changed through git and Argo CD, never with Helm. Its examples use a release that no Application renders. A test fails when a knowledge base page runs `helm rollback`, `helm uninstall` or `helm upgrade` against a release that an Application in `k8s/argocd/apps/` renders.
- The command and the AppProject are behavior a consumer observes, so the change carries a spec delta: the new capability `argo-helm-record-retirement`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `argo-helm-record-retirement`: which Helm release records `devops argo cd apps retire-helm-records` deletes, which it keeps, and that the AppProject reports a record that is left over.

## Impact

- New: `src/devops_cli/argo/helm_records.py`, `tests/test_argo_helm_records.py`.
- Changed: `src/devops_cli/commands/argo.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `k8s/argocd/apps/projects.yaml`, `k8s/README.md`, `src/devops_cli/ai/knowledge_base/it_domains/tools/helm.md`, `tests/test_k8s_argocd_apps.py`, and `tests/test_mcp.py`, whose list of commands that MCP does not expose now names the new command, because it deletes cluster Secrets.
- Regenerated: `docs/CLI_REFERENCE.md`, `docs/commands/argo.md`.

## Feasibility

Checked read-only on the homelab cluster on 2026-10-28, labels and metadata only, no Secret data read:

- `kubectl get secret -A -l owner=helm` returned 116 records:
  - 11 releases with 10 records each, their `deployed` record written from 2026-10-06T16:55:37Z to 16:56:09Z: `argocd`, `open-webui`, `qdrant`, `loki`, `dcgm-exporter`, `grafana`, `k8s-monitoring`, `prometheus-operator-crds`, `prometheus`, `pyroscope` and `otel-collector`;
  - `traefik` in `kube-system` with 2 records, `deployed` at 2026-09-30;
  - 4 `k8s-monitoring-alloy-*` records with an owner reference.
- Each of the 12 releases is rendered by the Application of the same name in its namespace. k3s has no `HelmChart` object, so no k3s helm-controller owns the `traefik` record.
- The cluster has 1,376 objects in the kinds that `kubectl api-resources --verbs=list,create` names, events left out. One `kubectl get` of all of them with `--show-managed-fields` and a metadata `jsonpath` took 8.8 s.
- Objects that a controller makes copy the release annotations of their owner, for example the ControllerRevisions of StatefulSet `qdrant`. So the check takes only top-level objects, those with no owner reference.
- No CustomResourceDefinition in the cluster carries an Argo CD tracking id; none of the 53 does. The three Argo CD CRDs (`applications`, `applicationsets` and `appprojects.argoproj.io`) list `argocd-controller` as a field manager with operation `Apply`. So a tracking id alone would refuse release `argocd` while Argo CD applies all of its objects. The field manager is the evidence for a CRD.
- With that rule, 11 releases qualify (102 records): `argocd`, `dcgm-exporter`, `grafana`, `k8s-monitoring`, `loki`, `open-webui`, `otel-collector`, `prometheus`, `pyroscope`, `qdrant` and `traefik`.
- `prometheus-operator-crds` does not qualify. Its 10 CRDs have the field managers `helm`, `k3s`, `kubectl-annotate` and `kubectl-label`, and no tracking id. Application `prometheus-operator-crds` is Synced and Healthy with an empty `status.history`: Argo CD never applied them.
- Argo CD documentation ("Helm", stable): "Helm is only used to inflate charts with `helm template`. The lifecycle of the application is handled by Argo CD instead of Helm." By default the release name is the Application name. FAQ: after a deploy with Argo CD, "you cannot use any Helm command to view/verify the application".
- Helm documentation ("Advanced Helm Techniques", storage backends): "By default, release information is stored in Secrets in the namespace of the release", selected with `-l owner=helm`. A Helm command acts only on a release whose records it finds.
- The runbooks that the issue names (`docs/agent/tasks/task-549`, `task-550`, `task-1080`) are no longer in the repository, so that part of the remedy is done.

## Existing Tool Considered

- **Helm:** Helm has no command that forgets a release and keeps its objects. `helm uninstall` deletes the objects, and `helm uninstall --keep-history` deletes them too and keeps only the records.
- **Argo CD:** Argo CD has no step that adopts a Helm release and drops its records. Its documentation says that Helm only renders the chart.
- **What the change uses:** kubectl, through the existing `run_subprocess` seam, with the selectors that Helm documents. It builds only the selection rule and the plan.
- **Cost of building:** about 60k tokens to build and test. Upkeep is small: the rule reads three documented markers (the Helm annotations, the tracking id and the field manager). Elapsed time is about two hours.
- **Deleted:** the `sh.helm.release.v1.*` orphan ignore and its pin in `tests/test_k8s_argocd_apps.py`, and the `helm rollback` and `helm uninstall` examples against `prometheus` in the knowledge base.
