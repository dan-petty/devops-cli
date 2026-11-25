# Tasks

## 1. Record the pin-policy ADR

Kind: docs. Reads: `docs/adr/README.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`, `k8s/argocd/image-updater-values.yaml`. Changes: `docs/adr/0040-renovate-pins-product-refs-to-release-tags.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`, `docs/adr/README.md`.

- [x] 1.1 Write `docs/adr/0040-renovate-pins-product-refs-to-release-tags.md`, amend `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md` metadata and `Status History`, and regenerate `docs/adr/README.md` with `devops docs generate`
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`

## 2. Verify ADR, docs, and k8s checks

Kind: docs. Reads: `docs/adr/0040-renovate-pins-product-refs-to-release-tags.md`, `k8s/argocd/image-updater-values.yaml`. Changes: none.

- [x] 2.1 Verify `tests/invariants/test_adr_records.py`, `devops docs check`, and `devops ci --check --skip test --force` (including `k8s`), and transition ADR `0040` to `accepted` with `body-hash` before marking the PR ready
  - Verification: `$ uv run devops ci --check --skip test --force`
