# Tasks

## 1. Documents

Kind: documents. Reads: `k8s/devops/cronjob-runner.yaml`, `k8s/devops/mcp-server/deployment.yaml`, `src/devops_cli/roadmap/release_comments.py`. Changes: `docs/roadmap/stage.md`, `k8s/devops/configmap.example.yaml`.

- [x] 1.1 Name the three images and the two checks in the verify screen section of `docs/roadmap/stage.md` and in the `ai` comment of `k8s/devops/configmap.example.yaml`
  - Verification: `$ ! git grep -n "only after the image" -- docs/roadmap/stage.md k8s/devops/configmap.example.yaml`
