# Design

## Decisions

- Record the policy in new ADR `0040` (`docs/adr/0040-renovate-pins-product-refs-to-release-tags.md`) with `issue: 5135`, `tracker: 5120`, and `amends: ["0013"]`.
- Update ADR `0013` only in front matter (`amended-by: ["0040"]`) and `## Status History` (`2026-11-25: Amended by ADR 0040, section Decision Outcome.`) so ADR `0013`'s recorded `body-hash` remains intact.
- Keep `k8s/argocd/image-updater-values.yaml` unchanged (`updateStrategy: digest`, `forceUpdate: true`, no `writeBackConfig`) and defer homelab Renovate configuration (`#6582`) and `workflowtemplate-version.yaml` (`#7141`).
- Regenerate `docs/adr/README.md` using `uv run devops docs generate`, write the draft PR with `status: proposed`, and set `status: accepted` plus computed `body-hash` once checks pass before marking the PR ready (`docs/adr/README.md`).

## Rejected alternatives

- Editing ADR `0013` in place: rejected because accepted ADR bodies are immutable and enforced by `body-hash` in `tests/invariants/test_adr_records.py`.
- Leaving the decision in issue comments only: rejected because ADR `0013` would remain the sole policy on `main`.
- Pinning manifests before the cutover or pinning manifests without image tags: rejected by the 2026-11-13 owner decision and `#4036`.
