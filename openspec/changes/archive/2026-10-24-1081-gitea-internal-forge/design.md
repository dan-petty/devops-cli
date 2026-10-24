# Design

## Context

The homelab runs every workload from Argo CD's leaf Applications, which track `main` (#755). `devops k8s deploy-stack` deploys the same manifests and charts on a cluster without Argo CD (#1675), pushes the Secrets of its stacks from the keyring (#741), and, on a cluster that Argo CD manages, writes the configured domain onto the hosts of the Applications `devops` and `ingress` as Kustomize patches (#1290). The repository is public and names hosts only under `example.com`. The Argo CD gate refuses the placeholder domain in a Helm values file (#1343).

Gitea is not deployed. The old in-cluster `registry:2` left in #1630, so the cluster has no internal registry until Gitea's container registry runs.

## Goals / Non-Goals

**Goals:**

- Run Gitea from its official chart under Argo CD, and from deploy-stack without Argo CD, as a writable forge with its container registry on.
- Serve it in the cluster over HTTP and to workstations at `https://git.<domain>` through the tunnel, with no domain in git.
- Keep its data from Argo CD, Helm and the scheduler, and lock it down: no SSH, no registration, no egress.
- Write its admin Secret from the keyring only.

**Non-Goals:**

- Point Argo CD or the pull-request images at Gitea (#1082), add the remotes and `gitea.url` (#1090), or back up its data.
- Apply anything to the cluster, store a secret, or change Cloudflare. A person does these after the merge.

## Decisions

- **Decision: the chart renders no Ingress; Application `ingress` renders the git host.**
  *Choice:* Ingress `gitea/gitea-ingress` with host `git.example.com` in `k8s/ingress/ingress-routes.yaml`, and `ingress.enabled: false` in the values.
  *Rejected alternative:* the chart's Ingress with host `git.example.com` in `k8s/gitea/values.yaml`, as the body says, or a homelab values file with the real domain.
  *Evidence for rejection:* `_check_helm_source` in `src/devops_cli/k8s/argocd_gate.py` refuses the placeholder domain in a values file, and `application_source` in `src/devops_cli/k8s/argocd_overrides.py` refuses an Application with `spec.sources`, so deploy-stack cannot patch a chart's host. A real domain in git breaks #1290.
- **Decision: `ROOT_URL` is the in-cluster address, and Gitea builds the public URLs per request.**
  *Choice:* `ROOT_URL: http://gitea-http.gitea.svc.cluster.local:3000/`, `DOMAIN: gitea-http.gitea.svc.cluster.local` and `PUBLIC_URL_DETECTION: auto`.
  *Rejected alternative:* `ROOT_URL: https://git.<domain>/` from a ConfigMap that deploy-stack renders, read through `gitea.additionalConfigFromEnvs` (the 2026-10-08 refinement).
  *Evidence for rejection:* Gitea 1.27.3 builds the clone URLs and the registry's token realm of a request from its `Host` header and `X-Forwarded-Proto` (`modules/httplib/url.go`), and the tunnel path keeps both (Cloudflare sets `X-Forwarded-Proto`, cloudflared forwards it, Traefik's `web` entrypoint trusts it). A ConfigMap would add deploy-stack code, an orphan entry and a pod that waits for it, for the links of non-request text only.
- **Decision: Gitea is a deploy-stack stack of its own, in `--stack all`.**
  *Choice:* stack `gitea` with the Helm repository `gitea-charts`, the release `gitea` and the perimeter file; its deploy sets the hosts of Application `ingress`.
  *Rejected alternative:* no deploy-stack entry, as the body says, or the `infra` stack.
  *Evidence for rejection:* #1675's tests require a deploy-stack counterpart for every Application and every NetworkPolicy. In `infra`, every deploy of `infra` would need the Gitea admin password, which a person types.
- **Decision: namespace `gitea` is in the root kustomization.**
  *Choice:* `k8s/namespaces.yaml`, as for every other stack.
  *Rejected alternative:* a `namespace.yaml` in `k8s/gitea/`, which only the Gitea deploy applies.
  *Evidence for rejection:* deploy-stack applies the root kustomization, then pushes the Secrets, then applies the stack's manifests. A namespace applied with the manifests does not exist at the push, so the first deploy installs a Gitea that waits for a Secret that the push skipped. A kustomization applied before the push would apply the Ingress with the placeholder host. The cost of this choice: `push-secrets` with no `--stack` needs the Gitea admin password on every cluster, and `teardown-stack --stack all` deletes the namespace and its data, as it does for the other stacks.
- **Decision: two Applications.**
  *Choice:* `gitea` (the chart and the `values` ref) and `gitea-manifests` (path `k8s/gitea`, the perimeter), as `argo-workflows` and `argo-workflows-manifests`.
  *Rejected alternative:* one Application with the chart, the `values` ref and the path.
  *Evidence for rejection:* `tests/test_k8s_argocd_apps.py` allows one git source in a multi-source Application, with `argocd` the only exception.
- **Decision: the admin user is the literal `gitea_admin`.**
  *Choice:* `LiteralSource("gitea_admin")`, the chart's default user.
  *Rejected alternative:* a setting `gitea.admin_username` with a check against Gitea's reserved names.
  *Evidence for rejection:* Gitea 1.27.3 does not reserve `gitea_admin` (`models/user/user.go`). A setting adds a config section and a hand-written copy of Gitea's reserved list for a name that is not secret.
- **Decision: SQLite in WAL mode, one pod, `Recreate`.**
  *Choice:* the body's database choice, made at the first install.
  *Rejected alternative:* the bundled PostgreSQL or Valkey charts.
  *Evidence for rejection:* they are Bitnami charts on `bitnamilegacy` images, which get no updates. Gitea does not support a later change of database type well, so the choice is made now.
- **Decision: the perimeter admits Argo CD's repo server now.**
  *Choice:* TCP 3000 from Traefik, `argocd-repo-server` and the namespace.
  *Rejected alternative:* add the repo server in #1082.
  *Evidence for rejection:* the body asks for it, and it opens no path that a later item must remove: Argo CD's own egress policy still blocks the connection until #1082 opens it.

## Risks / Trade-offs

- **Plain HTTP between nodes.** Flannel's `vxlan` backend carries pod traffic between nodes with no encryption. This holds for every host behind the tunnel; the owner accepted it.
- **No backups.** An issue or a pull request made in Gitea is lost with the node. A later item adds backups.
- **Cloudflare's request body limit.** A push of an image layer over 100 MB through the tunnel fails with 413. #1082 chooses the path of the pull-request images.
