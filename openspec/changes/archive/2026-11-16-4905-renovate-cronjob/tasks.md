# Tasks

## 1. Behavior

- [x] 1.1 Write the manifest invariant tests of `renovate-service`; they fail on the base (24 failed).
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_renovate.py`
- [x] 1.2 Add `k8s/devops/renovate/` (CronJob, ConfigMap, PVC, NetworkPolicy), the `renovate` entry of the default perimeter and of `kustomization.yaml`, and the four files of `deploy-stack --stack devops`.
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_renovate.py tests/config/test_k8s_devops_runtime.py tests/commands/k8s/test_k8s_network_policies.py`
- [x] 1.3 Add the Secret row `devops/renovate` and the orphan entry of the `homelab` AppProject.
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py tests/invariants/test_k8s_renovate.py`
- [x] 1.4 Check the rendered images (the pinned Renovate digest and the Service digest of Image Updater on the `token` init container) and the network policies.
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.5 Check the new files with Trivy: no HIGH or CRITICAL finding.
  - Verification: `$ trivy config --severity HIGH,CRITICAL --exit-code 1 k8s/devops/renovate/`

## 2. Documents

- [x] 2.1 Add ADR 0027, the exception in `CONTRIBUTING.md`, the Renovate section of `docs/CLUSTER.md`, and the rows, the note and the folder line of `k8s/README.md`.
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py tests/invariants/test_k8s_renovate.py`
- [x] 2.2 Write the generated ADR index again.
  - Verification: `$ uv run devops docs check`
