# Proposal

## Why

Issue #1081: the homelab has no internal forge. The owner wants a writable Gitea in the cluster for the iteration branches that do not go out to GitHub, and its container registry as the internal registry of the cluster. On 2026-10-24 the owner decided that the internal registry moves to Gitea (#1081, #1082, #1090, #1291, #1630). #1630 removed the old `registry:2`, so until Gitea runs, the cluster has no internal registry.

Pods and Argo CD reach Gitea in the cluster over HTTP at `http://gitea-http.gitea.svc.cluster.local:3000`. Workstations reach it at `https://git.<domain>` through the Cloudflare tunnel and Traefik. The admin credential lives in the keyring and reaches the cluster only through `devops k8s push-secrets`.

## What Changes

- Add `k8s/gitea/values.yaml` for chart `gitea` 12.7.0 from `https://dl.gitea.com/charts/` (Gitea 1.27.3, rootless image): one pod with `Recreate`, SQLite in WAL mode, sessions in the database, the bundled PostgreSQL and Valkey charts off, a 10Gi `local-path` claim that Argo CD and Helm keep, the control-plane `DoesNotExist` node affinity (#1634), non-root security contexts with a read-only root filesystem, bounded resources, no SSH, no registration, private repositories, no push-to-create, no migrations, no mirrors, no Actions, no update checker, and packages (the container registry) on. The admin comes from Secret `gitea-admin`.
- Add `k8s/gitea/networkpolicy.yaml` and `k8s/gitea/kustomization.yaml`: a default-deny perimeter that admits TCP 3000 only from Traefik, Argo CD's repo server and the namespace, and lets Gitea reach only DNS and the namespace.
- Add namespace `gitea` (Pod Security `restricted`, `Prune=false,Delete=false`) to `k8s/namespaces.yaml`, and Ingress `gitea/gitea-ingress` for host `git.example.com` to `k8s/ingress/ingress-routes.yaml`. deploy-stack sets the configured domain on that host, as on every other host (#1290).
- Add the Argo CD Applications `gitea` (the chart and the values file) and `gitea-manifests` (the perimeter), in project `homelab`. The AppProject `homelab` admits the chart repository and namespace `gitea`, and ignores the pushed Secret `gitea-admin` as an orphan. The AppProject `homelab-system` admits namespace `gitea` for the Ingress that Application `ingress` renders.
- Add the deploy-stack stack `gitea`: the Helm repository, the release and the perimeter, in `--stack all` too. Its deploy sets the hosts of Application `ingress` on a cluster that Argo CD manages.
- Add the push-secrets row `gitea/gitea-admin` (stack `gitea`): `username` is the literal `gitea_admin`, and `password` comes from the keyring key `gitea_admin_password`, which backs the new managed option `gitea.admin_password` (`DEVOPS_CLI_GITEA_ADMIN_PASSWORD`). The push never generates it. A change restarts `deployment/gitea`.
- Document Gitea in `k8s/README.md` (addresses, Cloudflare, rollout, password rotation, data, chart upgrade), and update the stack lists, the Cluster Secrets table, the tunnel diagram, the directory tree and the Internal Image Registry section. Update the stack lists in the knowledge base and `docs/DEVCONTAINER_USAGE.md`, and regenerate the command and environment documentation.
- The manifests, the push-secrets row, the option and the stack are observable behavior, so the change has a spec delta: the new capability `gitea-forge`, and an added requirement in `cluster-image-registry`.
- This change fits in one pull request: it adds YAML, one stack's table entries, one Secret row and one option, with offline tests.

## Capabilities

### New Capabilities

- `gitea-forge`: how the cluster runs Gitea, the internal forge: its Applications and stack, its values, its perimeter, its git host and its admin Secret.

### Modified Capabilities

- `cluster-image-registry`: an added requirement that Gitea's container registry is on.

## Impact

- `k8s/gitea/` (new), `k8s/namespaces.yaml`, `k8s/ingress/ingress-routes.yaml`, `k8s/argocd/apps/gitea.yaml` and `k8s/argocd/apps/gitea-manifests.yaml` (new), `k8s/argocd/apps/projects.yaml`.
- `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/commands/k8s/networking.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/options.py`, `src/devops_cli/config/env.py`, `src/devops_cli/security/secrets.py`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/lang/en/help.py`.
- `tests/test_k8s_gitea.py` (new), `tests/test_k8s_network_policies.py`, `tests/test_third_party_telemetry.py`, `tests/test_k8s_push_secrets.py`, `tests/test_k8s_devops_stack.py`, `tests/test_config_audit_keys.py`.
- `k8s/README.md`, `docs/DEVCONTAINER_USAGE.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md`, and the generated `docs/CLI_REFERENCE.md`, `docs/commands/k8s.md` and `docs/ENV_VARS.md`.
- `devops k8s push-secrets` with no `--stack` now pushes `gitea/gitea-admin` too, because the root kustomization creates namespace `gitea` on every cluster. It needs the Gitea admin password in the keyring. A deploy of another stack never reads it.
- The live cluster after the merge: Application `base` creates namespace `gitea`, and the Applications `gitea` and `gitea-manifests` sync. The Gitea pod waits in `CreateContainerConfigError` until a person pushes Secret `gitea-admin`.

## Feasibility

Checked on 2026-10-24 against the repository at `df8e2ee5`, the upstream chart and source, and read-only commands on the homelab cluster (Argo CD v3.5.3, k3s v1.31.4):

- **Chart and image.** `https://dl.gitea.com/charts/index.yaml` lists 12.7.0 (2026-07-19, appVersion 1.27.0) as the newest chart. Gitea 1.27.3 (2026-08-29) is the newest patch of that line; Gitea 28.2.0 is out, but only the chart's main branch (version 0.0.0, appVersion 28.0.0) supports it. `docker.gitea.com/gitea:1.27.3-rootless` answers 200. The pulled 12.7.0 chart's `values.yaml` and `templates/_helpers.tpl` set every key in this change: `postgresql-ha` and `valkey-cluster` are on by default, `strategy` is top-level, `persistence` is on, the admin Secret keys are `username` and `password`, and the chart's connection test is a `busybox:latest` pod. `helm template` (Helm v4.3.0) with `k8s/gitea/values.yaml` renders three Secrets, the claim, the `gitea-http` and `gitea-ssh` Services and the Deployment, with `Recreate`, the node affinity, the security contexts that Pod Security `restricted` requires on every container, and the `app.ini` sections that the tests assert.
- **Domain (#1290).** The body's `k8s/overlays/homelab/gitea/values.yaml` with `git.<domain>` conflicts with #1290: no file under `k8s/` names the homelab domain. The body's `git.example.com` in the chart's Ingress conflicts with the Argo CD gate of #1343 (`_check_helm_source` refuses the placeholder domain in a values file), and deploy-stack's host patches apply only to an Application with one `spec.source` (`application_source` refuses `spec.sources`). So the Ingress is a plain manifest in `k8s/ingress/ingress-routes.yaml`, which Application `ingress` renders and deploy-stack patches with the configured domain, and the chart renders no Ingress.
- **ROOT_URL.** The body sets `ROOT_URL: https://git.<domain>/`, and the 2026-10-08 refinement proposes a ConfigMap from deploy-stack. Neither is needed. Gitea 1.27.3 `modules/setting/server.go` defaults `PUBLIC_URL_DETECTION` to `auto`, and `modules/httplib/url.go` `GuessCurrentHostURL` builds the URL of a request from its `Host` header and `X-Forwarded-Proto`. `ComposeHTTPSCloneURL` (the API's `clone_url`) and the container registry's token realm (`routers/api/packages/container/container.go`) use it. Cloudflare sets `X-Forwarded-Proto` to the visitor's protocol (Cloudflare HTTP headers reference), cloudflared does not change it (no reference in its source), the tunnel's wildcard route has no `httpHostHeader` (`devops cloudflare tunnel routes`), and Traefik's `web` entrypoint has `forwardedHeaders.insecure: true`. So `ROOT_URL` is the in-cluster address, and a request through the tunnel gets `https://git.<domain>/` URLs. Only text that Gitea writes outside a request, such as the links a push prints, uses the in-cluster address.
- **#755 and #741.** The leaf Applications track `main` with the finalizer, automated prune and self-heal, and `retry` with backoff (`k8s/argocd/apps/*.yaml`). `tests/test_k8s_argocd_apps.py` allows one git source (`ref: values`) in a multi-source Application, so the perimeter is a second Application, `gitea-manifests`, as `argo-workflows-manifests` is. The push table (`src/devops_cli/k8s/cluster_secrets.py`) has `LiteralSource` and `KeyringSource` with a managed option, and a test fails on a Secret that a values file references without a row.
- **#1675.** The body says `_HELM_RELEASES_BY_STACK` gets no Gitea entry. `test_every_application_in_argocd_apps_maps_to_deploy_stack_counterpart` and the NetworkPolicy parity test (#1675, #1673) now require a deploy-stack counterpart for every Application and policy, so Gitea is the deploy-stack stack `gitea`.
- **Namespace.** Every namespace of the stacks is in `k8s/namespaces.yaml`, which deploy-stack applies before the Secret push (step 4 before step 5 of `deploy_stack`). A namespace outside it would exist only after the push, so the first deploy would install a Gitea that waits for its Secret. So `gitea` is in `k8s/namespaces.yaml`, and the stack is not a detached stack: its rows are pushed only by `push-secrets` with no stack or `--stack gitea`, and by `deploy-stack --stack gitea` or `all`.
- **Admin user.** The body takes the user name from a setting `gitea.admin_username` that must not be a reserved name. Gitea 1.27.3 `models/user/user.go` does not reserve `gitea_admin`, the chart's default, so the row uses that literal, as `grafana-admin` uses `admin`, and needs no setting and no reserved-name check.
- **Live cluster (read-only).** `kubectl get ns gitea` is NotFound. Storage class `local-path` (`rancher.io/local-path`, reclaim `Delete`) is the default, and one of the four nodes has the control-plane role. Traefik's pods carry `app.kubernetes.io/name=traefik` in `kube-system`, and the repo server's pods carry `app.kubernetes.io/name=argocd-repo-server` in `argocd`. `devops cloudflare tunnel routes` shows the wildcard route to `http://traefik.kube-system.svc.cluster.local:80`, and `devops cloudflare access status` shows a self-hosted Access application for the wildcard. So `git.<domain>` needs no new route, DNS record or Access application.
- **A limit for #1082.** Cloudflare refuses a request body over the limit of the plan (100 MB on the Free and Pro plans) with 413 (Cloudflare limits page), so a push of a larger image layer through `https://git.<domain>` fails. The container runtime of a node resolves names with the node's DNS, not the cluster's, so it cannot pull from the in-cluster address. #1082 chooses the push and pull path of the pull-request images.

## Existing Tool Considered

Gitea's official Helm chart (`gitea.com/gitea/helm-gitea`, three named maintainers, releases from 12.1.1 on 2025-06-27 to 12.7.0 on 2026-07-19) runs Gitea, and Gitea's own packages feature is the container registry. Argo CD deploys it, deploy-stack's existing Kustomize host patches set its host, and the existing push-secrets table writes its Secret. Gitea's `PUBLIC_URL_DETECTION = auto` builds the public URLs, so the change adds no ConfigMap and no domain template. The change adds data rows only (a stack's table entries, one Secret row and one option), and no new function.

The change deletes no internal code.
