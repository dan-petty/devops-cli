# Tasks

## 1. Remove the confirmation text

Kind: other

Changes: `k8s/devops/valkey-roadmap/kustomization.yaml`, `docs/HOMELAB_REPO_SWITCH.md`.

- [x] 1.1 Remove the comment and the `Prune=true` generator annotation of the Valkey kustomization.
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Add the paragraph to step 13 of the switch document.
  - Verification: `$ uv run devops ci --check --only docs`
