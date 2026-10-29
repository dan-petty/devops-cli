# Tasks

## 1. Traefik runs a chart that ships v3.7.16

- [x] Add a failing test: the Traefik Application pins chart `traefik` from `https://traefik.github.io/charts` at 42.1.1 or later, and the values set no image tag
  - Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py`
- [x] Add a test that fails when `deploy-stack` installs a chart at another version than an Application pins
  - Verification: `uv run devops ci test tests/test_k8s.py`
- [x] Pin chart 42.1.3 in `k8s/argocd/apps/traefik.yaml` and in `_HELM_RELEASES_BY_STACK`, and name chart 42.1.3 in `_CHART_TOKENS` after reading its pods from the 42.1.3 render
  - Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/test_k8s.py`

## 2. Renovate proposes the chart pins of the Applications

- [x] Add failing tests: the `argocd` manager's patterns match every file that holds an Application with a chart source, its pull requests carry `type/chore` and `scope/infra`, and its `git-tags` dependencies are off
  - Verification: `uv run devops ci test tests/test_renovate_config.py`
- [x] Give the `argocd` manager its pattern and rules in `.github/renovate.json`
  - Verification: `uv run devops ci test tests/test_renovate_config.py`
- [x] Describe the `argocd` manager and the two checks of a chart update in `docs/SDLC.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1659-traefik-chart-renovate`

## Workflow follow-up

- Pending a person: after Argo CD syncs the merge, check that Deployment `kube-system/traefik` runs `docker.io/traefik:v3.7.16` and that the Ingress hosts answer through the tunnel.
- Pending a person: check that Renovate's next run reports no configuration error and lists the chart pins of the Applications on its dependency dashboard.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
