# Tasks

## 1. Test the Crawl4AI manifests, the perimeters and the scan job

Kind: behavior.

Reads: `k8s/devops/networkpolicy.yaml`, `tests/support/k8s_tree.py`. Changes: `tests/commands/k8s/test_k8s_network_policies.py`, `tests/k8s/test_image_pins.py`, `tests/invariants/test_workflow_contracts.py`. Creates: `tests/invariants/test_k8s_crawl4ai.py`.

- [x] 1.1 Write `tests/invariants/test_k8s_crawl4ai.py`: the image pin, the replica and strategy, the `restricted` controls, the volumes, the environment, the probes, the resources, the Service, no route, and the three lists that name the files
  - Verification: `uv run devops ci test tests/invariants/test_k8s_crawl4ai.py` fails on the base
- [x] 1.2 In `tests/commands/k8s/test_k8s_network_policies.py`, add the cases for the default perimeter, `crawl4ai-perimeter` (ingress and egress), the removed ranges, and the one sender to port 11235
  - Verification: `uv run devops ci test tests/commands/k8s/test_k8s_network_policies.py` fails on the base
- [x] 1.3 In `tests/k8s/test_image_pins.py`, add a case that an image with a tag and a digest is a pin that resolves by its digest
  - Verification: `uv run devops ci test tests/k8s/test_image_pins.py` passes
- [x] 1.4 In `tests/invariants/test_workflow_contracts.py`, add the job `third-party-image-scan` to the list of Trivy scans and a case for its exit code and paths filter
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py` fails on the base

## 2. Add the manifests and the scan job

Kind: other.

Reads: `k8s/devops/roadmap-service/deployment.yaml`, `k8s/llm/portkey/networkpolicy.yaml`. Changes: `k8s/devops/networkpolicy.yaml`, `k8s/devops/kustomization.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/k8s/cluster_secrets.py`, `.github/workflows/ci.yml`. Creates: `k8s/devops/crawl4ai/deployment.yaml`, `k8s/devops/crawl4ai/service.yaml`, `k8s/devops/crawl4ai/networkpolicy.yaml`, `k8s/devops/crawl4ai/networkpolicy-client.yaml`, `k8s/devops/crawl4ai/kustomization.yaml`.

- [x] 2.1 Add the five files of `k8s/devops/crawl4ai/`, make the default perimeter skip the pod, and list the folder in `k8s/devops/kustomization.yaml` and the four manifests in `MANIFESTS_BY_STACK["devops"]`
  - Verification: `uv run devops ci test tests/invariants/test_k8s_crawl4ai.py tests/commands/k8s/test_k8s_network_policies.py tests/invariants/test_k8s_argocd_apps.py` passes
- [x] 2.2 Add the job `third-party-image-scan` to `.github/workflows/ci.yml`
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py` passes

- [x] 2.3 Add `restarts=(Workload("deployment", "crawl4ai"),)` to Secret `devops/crawl4ai`, so a new token restarts the pod, and show it in the Cluster Secrets table of `k8s/README.md`
  - Verification: `uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/invariants/test_k8s_manifests.py` passes

## 3. Document the service

Kind: other.

Reads: `k8s/README.md`, `docs/SDLC.md`. Changes: `k8s/README.md`, `docs/SDLC.md`.

- [x] 3.1 Add the section "Crawl4AI" and the directory tree to `k8s/README.md`, and the job to `docs/SDLC.md`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: create Secret `crawl4ai` with `uv run devops k8s push-secrets --stack devops` before the first sync. The pod cannot start without it.
- Pending a person: after the sync, check that the pod is Ready and run the live check of #3894.
