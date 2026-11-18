# Proposal: #5303

## Why

Argo CD reports the ConfigMap `cnpg-default-monitoring` as an orphan in the Applications `llm`,
`open-webui`, `qdrant` and `mattermost`. The CloudNativePG operator copies its default monitoring
queries into each namespace that has a Cluster. The copy has the label
`app.kubernetes.io/managed-by=cloudnative-pg`, no `ownerReferences` and no Argo CD tracking id, so
Argo CD sees a resource that no Application tracks. The AppProject `homelab` warns on orphans
(`k8s/argocd/apps/projects.yaml`) and its ignore list holds no such name, so the warning hides a
real orphan among the expected ones. Closes #5303.

## What Changes

- The `homelab` AppProject ignore list gains `{group: '', kind: ConfigMap, name:
  cnpg-default-monitoring}`, so Argo CD reports no orphan for the operator-written ConfigMap.
- The `homelab` project keeps `orphanedResources.warn` true, so Argo CD still reports other
  orphans.
- The gateway Cluster keeps the default CloudNativePG queries: no `disableDefaultQueries` is set,
  so `cnpg_collector_up` and the default metrics keep their samples.

## Capabilities

`homelab-project-destinations` (modified): the `homelab` AppProject ignores the CloudNativePG
monitoring ConfigMap, and keeps its orphan warning on.

## Impact

- The four Applications show no `OrphanedResourceWarning` for the ConfigMap after the sync.
- The ConfigMap stays in place and the database alerts keep their samples.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: `k8s/argocd/apps/projects.yaml` holds the `homelab` AppProject with
  `orphanedResources.warn: true` and an `ignore` list, and `k8s/llm/gateway-db.yaml` sets no
  `disableDefaultQueries`. Argo CD defines an ignore rule by group, kind and name with no namespace
  field, so one entry matches the ConfigMap in every namespace
  (https://argo-cd.readthedocs.io/en/stable/user-guide/orphaned-resources/).

## Existing Tool Considered

argoproj/argo-cd (Apache-2.0, maintained, last activity 2026-11-16) is already in use, and its
AppProject `orphanedResources.ignore` covers the need. The tool lacks a way to stop the
CloudNativePG operator from writing the per-namespace ConfigMap and adds no `ownerReferences` or
tracking id to it, so the ignore list is the only fix. No new component is built.
