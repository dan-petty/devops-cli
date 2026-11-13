# Tasks

## 1. Declare the measured pod overhead of RuntimeClass gvisor

Kind: manifest. Changes: `k8s/runtimeclass-gvisor.yaml`, `tests/invariants/test_k8s_argocd_apps.py`.

- [x] 1.1 `tests/invariants/test_k8s_argocd_apps.py::test_the_gvisor_runtime_class_declares_the_measured_pod_overhead` fails: RuntimeClass `gvisor` has no `overhead`.
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` fails on the base
- [x] 1.2 Set `overhead.podFixed` of RuntimeClass `gvisor` to memory `16Mi` with no `cpu` key, and replace the header line that blocks each workload until #5434 with a line that names the measured value. `kubectl apply --dry-run=server -f k8s/runtimeclass-gvisor.yaml` gives `configured (server dry run)`.
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` passes

## 2. Documents

Kind: other. Changes: `k8s/README.md`.

- [x] 2.1 In the section "gVisor Runtime" of `k8s/README.md`, give the kernel version of the pinned `runsc` in the bullet "Use", the measured result with a link to the comment of #5434 in the bullet "Limits", and the overhead `16Mi` in a new bullet "Overhead".
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #5447: the first workload of the class is a sandbox entry under this policy, and the owner approves it. This change moves no workload to the class.
- #4003, #5356 and #2695 (the runner Jobs): each item sets `runtimeClassName: gvisor` in its own pull request, after this change merges.
