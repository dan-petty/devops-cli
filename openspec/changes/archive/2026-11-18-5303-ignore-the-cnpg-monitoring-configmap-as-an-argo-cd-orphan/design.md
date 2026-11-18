# Design

## Decisions
- Add the entry to the AppProject `homelab` `spec.orphanedResources.ignore` list. It is Argo CD's
  own mechanism, and the project already uses it for operator-written Secrets and the
  `devops-cli-config` ConfigMap.
- Use the three fields `group: ''`, `kind: ConfigMap`, `name: cnpg-default-monitoring`. Argo CD
  defines an ignore rule by group, kind and name and has no namespace field, so one entry matches
  the ConfigMap in every namespace, and the four Applications are covered.
- Keep `orphanedResources.warn` true, so Argo CD still reports other orphans.

## Rejected alternatives
- Set `disableDefaultQueries` on the Clusters: it removes the default monitoring queries, so
  `cnpg_collector_up` and the `GatewayDatabaseDown` alert lose their samples.
- Patch the ConfigMap with an `ownerReference` or a tracking id: the CloudNativePG operator writes
  the ConfigMap and sets no `ownerReference`, so a patch is reverted.
- Add a namespace field to the rule: Argo CD's ignore rule has no namespace field, so it would not
  apply.
