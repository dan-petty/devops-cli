# Tasks

## 1. The renderer and its token

- [x] 1.1 Write failing tests: the Grafana values enable the renderer at a release tag with requests, limits, `GOMEMLIMIT` and the chart's ingress policy, and take the token from Secret `grafana-image-renderer`; no Ingress routes to the renderer; the renderer pod mounts no ServiceAccount token; the Secret table holds the token row, its keyring-only key and its restart targets; the README and the `deploy-stack` dry run list the row
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py tests/invariants/test_k8s_manifests.py tests/k8s/test_cluster_secret_plan.py tests/commands/k8s/test_k8s.py`
- [x] 1.2 Enable `imageRenderer` in `k8s/monitoring/grafana-values.yaml`, add the row `monitoring/grafana-image-renderer` to `src/devops_cli/k8s/cluster_secrets.py`, and add the Secret to the orphan ignore list of project `homelab`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py tests/invariants/test_k8s_manifests.py tests/k8s/test_cluster_secret_plan.py tests/commands/k8s/test_k8s.py`

## 2. Manifest check

- [x] 2.1 Render each Argo CD Application with the pinned charts and resolve each image, the renderer included
  - Verification: `$ uv run devops k8s image-pins`

## 3. Documents

- [x] 3.1 Describe the renderer, its resources, the render check in the light and the dark theme, and Secret `monitoring/grafana-image-renderer` in `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

- Pending a person: before the merge, push the token Secret from the branch with `uv run devops k8s push-secrets --only monitoring/grafana-image-renderer`, so that the Grafana pod finds it when Argo CD syncs.
- Pending a person: after the sync, render panel 11 of `devops-cli-telemetry` with `theme=light` and `theme=dark` (`get_panel_image` or the commands of `k8s/README.md`, Grafana Image Renderer), check that the working set of the renderer stays below 80 % of its memory limit over 10 renders in a row, and check that Argo CD shows the app `grafana` Synced and Healthy.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
