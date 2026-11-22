# Tasks

## 1. The pod renders its settings without the metrics Secret

Kind: behavior. Reads: `k8s/devops/searxng/deployment.yaml`, `k8s/devops/searxng/configmap.yaml`, `tests/gate/k8s_render.py`. Changes: `tests/gate/k8s_checks/searxng_render.py`, `k8s/devops/searxng/deployment.yaml`, `k8s/devops/searxng/configmap.yaml`.

- [x] 1.1 Write `tests/gate/k8s_checks/searxng_render.py`. It renders `k8s/devops/searxng/` with `kustomize`, takes the command, the arguments, the variables and the mounts of init container `render-settings`, gives each mount path a directory under `tmp_path` (the keys of a ConfigMap volume as files, an `emptyDir` empty), and runs the script with `sh`. A required reference to a Secret that the scenario leaves out fails as the kubelet fails it. `check_render_settings_without_the_metrics_secret_turns_the_endpoint_off` asserts exit 0, an empty `general.open_metrics` in the file that the `searxng` container mounts at `/etc/searxng/settings.yml`, and one log line that names `devops/searxng-metrics-auth`. `check_render_settings_with_the_metrics_secret_writes_its_password` asserts exit 0, a password with `&`, `\` and `|` in `general.open_metrics`, and no log line. The first check fails on the base, because the reference is required
  - Verification: `$ uv run devops ci --check --only k8s` fails on the base
- [ ] 1.2 In `k8s/devops/searxng/deployment.yaml`, give the `secretKeyRef` of `SEARXNG_METRICS_PASSWORD` `optional: true`. Change the script of `render-settings` to write `''` in place of the placeholder and to log one line to stderr that names Secret `devops/searxng-metrics-auth` when `${SEARXNG_METRICS_PASSWORD:-}` is empty, and else to write the escaped password as before. Change the comments of the init container and of `general.open_metrics` in `k8s/devops/searxng/configmap.yaml` to say so
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. The password of the metrics Secret is optional

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/invariants/test_k8s_manifests.py`. Changes: `tests/invariants/test_k8s_searxng.py`, `src/devops_cli/k8s/cluster_secrets.py`, `k8s/README.md`.

- [ ] 2.1 Extend `test_the_metrics_secret_row` in `tests/invariants/test_k8s_searxng.py` to assert that entry `password` is not required and that `OPTIONAL_FEATURE_SECRETS` names the row. The test fails on the base
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py` fails on the base
- [ ] 2.2 In `src/devops_cli/k8s/cluster_secrets.py`, set `required=False` on entry `password` of row `devops/searxng-metrics-auth`, change the comment of the row, and add the row to `OPTIONAL_FEATURE_SECRETS`. Change the row of key `password` in the Cluster Secrets table of `k8s/README.md` to the text that `test_readme_lists_the_table` computes
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py tests/invariants/test_k8s_manifests.py tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py tests/commands/k8s/test_k8s.py tests/k8s/test_grafana_renderer_optional.py` passes

## 3. The documents say that the Secret is optional

Kind: other. Reads: `k8s/README.md`, `docs/CLUSTER.md`. Changes: `k8s/README.md`, `docs/CLUSTER.md`.

- [ ] 3.1 In the paragraph of `devops/searxng-metrics-auth` under the Cluster Secrets table of `k8s/README.md`, say that the Secret is optional, what the pod does without it, and that a push with no keyring value skips the password. In the SearXNG section of `docs/CLUSTER.md`, change The secrets so that only Secret `searxng` is needed before the first sync, and add to The metrics what `render-settings`, `/metrics` and Alloy do while the Secret is missing
  - Verification: `$ uv run devops ci --check --only docs` passes

## Workflow follow-up

- Pending a person: run `devops k8s push-secrets --only devops/searxng-metrics-auth` to turn the OpenMetrics endpoint on; the push restarts `deployment/searxng`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
