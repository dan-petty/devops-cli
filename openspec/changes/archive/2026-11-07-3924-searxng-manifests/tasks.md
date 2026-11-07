# Tasks

## 1. Test the SearXNG manifests, the perimeters and the secret row

Kind: behavior.

Reads: `k8s/devops/networkpolicy.yaml`, `tests/support/k8s_tree.py`, `tests/invariants/test_k8s_crawl4ai.py`. Changes: `tests/commands/k8s/test_k8s_network_policies.py`, `tests/k8s/test_image_pins.py`, `tests/core/test_renovate_config.py`, `tests/invariants/test_k8s_manifests.py`, `tests/config/test_k8s_devops_runtime.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`. Creates: `tests/invariants/test_k8s_searxng.py`, `tests/fixtures/searxng/default_engine_names.txt`.

- [x] 1.1 Write `tests/invariants/test_k8s_searxng.py` and the names file: the image pin, the names file tag, the `restricted` controls, the environment, the secret row, the probes, the resources, the Service, no route, the settings, the kept engines, the forbidden engines, and the lists that name the files
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py` fails on the base
- [x] 1.2 In `tests/commands/k8s/test_k8s_network_policies.py`, add the cases for `searxng-perimeter` (ingress and egress) and the one sender to port 8080, and change the case of the default perimeter to skip both pods
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_network_policies.py` fails on the base
- [x] 1.3 In `tests/k8s/test_image_pins.py`, add a case that an image with `docker.io`, a date tag and a digest is a pin that resolves by its digest
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py` passes
- [x] 1.4 In `tests/core/test_renovate_config.py`, add the case for the note of the SearXNG rule
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py` fails on the base
- [x] 1.5 Update the cases that count the manifests, the keyring-only keys, the secret rows and the default perimeter selector
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py tests/config/test_k8s_devops_runtime.py tests/commands/k8s/test_k8s_devops_stack.py tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py` fails on the base

## 2. Add the manifests, the secret row and the Renovate rule

Kind: other.

Reads: `k8s/devops/crawl4ai/`. Changes: `k8s/devops/networkpolicy.yaml`, `k8s/devops/kustomization.yaml`, `k8s/argocd/apps/projects.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/k8s/cluster_secrets.py`, `.github/renovate.json`. Creates: `k8s/devops/searxng/configmap.yaml`, `k8s/devops/searxng/deployment.yaml`, `k8s/devops/searxng/service.yaml`, `k8s/devops/searxng/networkpolicy.yaml`, `k8s/devops/searxng/networkpolicy-client.yaml`, `k8s/devops/searxng/kustomization.yaml`.

- [x] 2.1 Add the six files of `k8s/devops/searxng/`, make the default perimeter skip the pod, and list the folder in `k8s/devops/kustomization.yaml` and the five manifests in `MANIFESTS_BY_STACK["devops"]`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py tests/commands/k8s/test_k8s_network_policies.py tests/invariants/test_k8s_argocd_apps.py`
- [x] 2.2 Add the row `devops/searxng` to the cluster secrets and Secret `searxng` to the orphaned-resource ignore list of the Argo CD project
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py tests/invariants/test_k8s_manifests.py`
- [x] 2.3 Add the Renovate rule for the image
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`

## 3. Document the service

Kind: other.

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 3.1 Add the table row, the note on the secret, the section "SearXNG" and the directory tree to `k8s/README.md`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py`

## Workflow follow-up

- Pending a person: create Secret `searxng` with `uv run devops k8s push-secrets --stack devops` before the first sync. The pod cannot start without it.
- Pending a person: set `search.searxng_url` in the live ConfigMap when the pod is Ready.
- Work not done here: the live check of the network policies and of the pod on the cluster is the work of #3929.
