# Proposal: #4764

## Why

CloudNativePG removes the in-tree `barmanObjectStore` in 1.32.0, so the gateway database (#3741) and the Mattermost database can back up only through the CloudNativePG Barman Cloud plugin. The plugin needs cert-manager, and the cluster runs neither. Closes #4764.

## What Changes

- Argo CD Application `cert-manager`: chart `jetstack/cert-manager` v1.21.3 in namespace `cert-manager`, with values that keep the CRDs and keep the leader election lease in the namespace of the release.
- Argo CD Application `plugin-barman-cloud`: chart `cloudnative-pg/plugin-barman-cloud` 0.8.1 (plugin v0.15.1) in `cnpg-system`, the namespace of the operator. It syncs in wave 1, after `cert-manager`, and skips the dry run of a kind that has no CRD yet.
- AppProject `homelab-system` allows `https://charts.jetstack.io` and namespace `cert-manager`. AppProject `homelab` allows namespace `cert-manager`, because Application `base` applies its perimeter.
- Namespace `cert-manager` with Pod Security `restricted`.
- NetworkPolicies: a default-deny perimeter of `cert-manager` (the metrics scrape of `monitoring` in on 9402; CoreDNS and the API server out), a webhook policy (TCP 10250 in from any peer, on the webhook pods alone), and a policy on the plugin pod in `cnpg-system` (the operator in on 9090; CoreDNS and the API server out). The monitoring perimeter lets Alloy scrape cert-manager on 9402.
- `devops k8s deploy-stack --stack infra` installs `cert-manager` and then `plugin-barman-cloud` after `cloudnative-pg`. The release table and the Helm repository table get the two charts.
- The claim table of the local-path placement test names the two charts. `k8s/README.md` gets the section "CloudNativePG Backup Plugin" and the new rows and tree entries.

These are manifests and deploy-stack behavior, which a consumer observes, so the change carries spec deltas for `k8s-helm-deploy` and `k8s-network-policies`. No database uses the plugin in this change: the backup items add an `ObjectStore` and the `plugins` entry of each `Cluster`. The change fits one pull request.

## Capabilities

- `k8s-helm-deploy`: ADDED requirement for the install order of cert-manager and the plugin.
- `k8s-network-policies`: ADDED requirements for the cert-manager and plugin perimeters.

## Impact

- Two new Helm releases in stack `infra`: four Deployments and one start-up Job, with small requests (10m CPU each).
- Two new CRD groups in the cluster: `cert-manager.io` and `acme.cert-manager.io` (kept when the release goes) and `barmancloud.cnpg.io`.
- The live cluster changes only when the pull request merges and Argo CD syncs. The pull request comment lists the live steps and checks.

## Feasibility

All checks ran on 2026-11-11 on `origin/main` at `c9513687`.

- In-tree removal: the CloudNativePG `release-1.30` branch, `docs/src/appendixes/backup_barmanobjectstore.md`, says that 1.31 is the last minor release with native Barman Cloud support and that 1.32.0 removes it.
- Plugin requirements: `web/docs/intro.md` of plugin-barman-cloud at tag `v0.15.1` asks for CloudNativePG 1.26 or later and cert-manager. `web/docs/installation.mdx` says the plugin must run in the namespace of the operator. The cluster runs operator 1.30.1 from chart `cloudnative-pg` 0.29.1 in `cnpg-system`.
- How the parts talk: `web/docs/concepts.md` at `v0.15.1` says that sidecar containers in the instance pod run the backups and the WAL archive. So the instance pods need no network rule to the plugin pod. The CloudNativePG operator calls the plugin through Service `barman-cloud` on port 9090; the rendered chart carries `cnpg.io/pluginName: barman-cloud.cloudnative-pg.io` and `cnpg.io/pluginPort: "9090"` on that Service.
- Release ages, from the GitHub releases API: cert-manager v1.21.3 was published on 2026-10-23 (19 days), and no newer v1.21 or v1.22 release exists. plugin-barman-cloud v0.15.1 was published on 2026-09-30 and chart `plugin-barman-cloud-v0.8.1` on 2026-09-30 (42 days). v0.16.0 (2026-11-09) and chart 0.9.0 (2026-11-09) are too young for the 14-day rule.
- Licenses, from the GitHub license API: `cert-manager/cert-manager`, `cloudnative-pg/plugin-barman-cloud` and `cloudnative-pg/charts` are all Apache-2.0.
- Rendered charts: `helm template` of both charts at the pinned versions, with the values of this change, gives these facts. The pods carry the labels that the policies select (`app.kubernetes.io/name: webhook` and `app.kubernetes.io/component: webhook`; `app.kubernetes.io/name: plugin-barman-cloud`). The webhook listens on 10250. The three cert-manager pods have `prometheus.io/port: "9402"`. All leader election Roles are in `cert-manager`. Every container meets Pod Security `restricted` (non-root, `RuntimeDefault` seccomp, no privilege escalation, all capabilities dropped). The CloudNativePG operator pods carry `app.kubernetes.io/name: cloudnative-pg`.
- Argo CD (`docs/user-guide/helm.md`, branch `stable`) reads `helm.sh/resource-policy: keep` as `Delete=false`, so the kept cert-manager CRDs stay also when the Application goes.
- The new tests fail on the base for the right reason: 19 tests fail because the files, the namespace, the releases and the Applications do not exist.

## Existing Tool Considered

cert-manager and the CloudNativePG Barman Cloud plugin are the open, maintained tools for this need. Both are Apache-2.0. They are the upstream path after the in-tree removal, so this change adds only their configuration and no custom code. A `pg_dump` CronJob was rejected: it has no WAL archive and no point-in-time recovery, which #3741 needs. The change deletes no internal code.
