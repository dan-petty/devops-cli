# Proposal

## Why

Issue #1659: Traefik runs v3.7.13 from chart 41.6.0. Later Traefik releases fix twelve security advisories against v3.7.13, but nothing proposes a chart update: Renovate's `argocd` manager has no default file patterns, so it reads no Argo CD Application under `k8s/argocd/apps/`. The chart pins stay where a person last put them.

## What Changes

- The Argo CD Application `traefik` (`k8s/argocd/apps/traefik.yaml`) pins chart 42.1.3, which ships Traefik v3.7.16. The issue named 41.7.1 (v3.7.14). Since the issue was written, v3.7.15 and v3.7.16 fixed four more advisories, and chart 41.7.1 is the last 41.x chart, so only chart 42 carries them.
- `devops k8s deploy-stack` installs Traefik at the same chart version (`_HELM_RELEASES_BY_STACK` in `src/devops_cli/commands/k8s/stack_lifecycle.py`).
- `_CHART_TOKENS` in `tests/invariants/test_k8s_manifests.py` names chart 42.1.3. Its Traefik pods were read again from the 42.1.3 render, and they did not change.
- `.github/renovate.json` gives the `argocd` manager the pattern `^k8s/argocd/apps/.+\.ya?ml$`, labels its pull requests `type/chore` and `scope/infra`, and turns off its `git-tags` dependencies: Renovate reads a source with no chart, such as the `ref: values` source and the path sources that track `main`, as a git dependency, and Argo CD tracks `main` on purpose (ADR 0013).
- A new test fails when `deploy-stack` installs a chart at another version than the Application pins. Renovate moves only the Application pins, so without this check the two paths would run different releases after the first chart update.
- `docs/SDLC.md` describes the `argocd` manager and the two checks that a chart update must pass.
- The Application pin and the version that `deploy-stack` installs are observable, so the change carries spec deltas: the new capability `traefik-release-pin`, and an ADDED requirement in `k8s-helm-deploy`. The Renovate configuration and the tests change no behavior a consumer sees.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `traefik-release-pin`: the Traefik chart that the Argo CD Application installs ships a Traefik release with every published v3.7.x security fix.

### Modified Capabilities

- `k8s-helm-deploy`: `deploy-stack` installs each chart at the version that its Argo CD Application pins.

## Impact

- `k8s/argocd/apps/traefik.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `.github/renovate.json`, `docs/SDLC.md`.
- `tests/invariants/test_k8s_manifests.py`, `tests/test_renovate_config.py`, `tests/test_k8s.py`.

## Feasibility

- Live cluster, read-only, 2026-10-29: Deployment `kube-system/traefik` runs `docker.io/traefik:v3.7.13` with label `helm.sh/chart=traefik-41.6.0`. Application `traefik` is Synced and Healthy. The arguments name only the `kubernetescrd` and `kubernetesingress` providers and no experimental feature. The one Middleware in the cluster is a `rateLimit`, and no manifest under `k8s/` sets `forwardAuth`. Kubernetes is v1.31.4 (k3s), and minikube v1.39.0 starts v1.37.0 by default (`minikube start --help`, "stable").
- `helm search repo traefik/traefik --versions` (2026-10-29): 41.6.0 and 41.6.1 ship v3.7.13; 41.7.0, 41.7.1 and 42.0.0 ship v3.7.14; 42.1.0 ships v3.7.15; 42.1.1, 42.1.2 and 42.1.3 ship v3.7.16. 42.1.3 is the newest chart.
- Traefik release notes (github.com/traefik/traefik/releases): v3.7.14 (2026-10-06) fixes GHSA-53qr-784g-cj35, -cw35-4q88-3rmp, -fh26-gfpp-7xxx, -mwrr-6hp4-pxr6, -qm9f-w54v-q2qh, -qvj7-gq9c-hp7q, -rv2h-qh7j-xrjw and -mhjw-hmjv-p99x. v3.7.15 (2026-10-15) fixes GHSA-p8wx-ph99-xgcr (Ingress-NGINX provider mTLS), GHSA-ww7c-q3mv-xx22 (experimental FastProxy) and GHSA-28hp-c82p-8vqj (Ingress-NGINX provider cross-namespace CA secret), and rejects CONNECT requests at the server. v3.7.16 (2026-10-20) fixes GHSA-hrpp-p4fc-wwf8 (ForwardAuth with an NTLM or Negotiate auth server). Each advisory needs a feature that this cluster does not use (the Ingress-NGINX provider, FastProxy, NTLM or Negotiate backends, ForwardAuth, or a Go 1.27 build). The upgrade is hygiene, not an incident fix.
- Chart 42.0.0 (github.com/traefik/traefik-helm-chart/releases, 2026-10-15) has three breaking changes: Kubernetes v1.30 or later, Traefik Hub Secret write verbs scoped to the release namespace, and Traefik Hub transparency-log witness defaults. Both clusters run v1.30 or later, and `k8s/ingress/traefik-values.yaml` sets no `hub` value. Charts 42.1.0 to 42.1.3 add only the Traefik and Traefik Hub updates and `imagePullSecrets` support.
- `helm template traefik traefik/traefik --include-crds -f k8s/ingress/traefik-values.yaml` (Helm v4.3.0) at 41.6.0 and at 42.1.3 gives 9,031 lines each. The two renders differ in 16 lines only: the image `docker.io/traefik:v3.7.13` becomes `v3.7.16`, and seven `helm.sh/chart` labels move from `traefik-41.6.0` to `traefik-42.1.3`. The CRDs, the RBAC, the ServiceAccount (`automountServiceAccountToken: false`), the pod token (`true`) and the ClusterRole `traefik-kube-system` are the same.
- Renovate's `argocd` manager (docs.renovatebot.com/modules/manager/argocd/): "The `argocd` manager has no default `managerFilePatterns` pattern". Its source (`lib/modules/manager/argocd/extract.ts`) skips a file without an `argoproj.io` apiVersion, reads `spec.source` and every entry of `spec.sources`, makes a `helm` dependency from `repoURL`, `chart` and `targetRevision`, and makes a `git-tags` dependency from a source with no chart.
- The repository's other chart pins already agree: each of the 15 `deploy-stack` releases installs the version that its Application pins (measured before the change).
- `renovate-config-validator` was not run: this session may not run code that it downloads. Renovate checks its configuration on each run and opens an issue when it finds an error, so the first run after the merge is the check.

## Existing Tool Considered

Renovate is the tool that proposes the chart updates; the change only gives its `argocd` manager the files to read. It builds no update mechanism. The rejected alternative, `deploy-stack` reading each version from the Application at run time, is in `design.md`. The change deletes no code.
