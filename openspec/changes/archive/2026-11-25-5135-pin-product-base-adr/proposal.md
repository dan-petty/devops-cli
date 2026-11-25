# Proposal: #5135

## Why

[ADR 0013](docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md) states that Argo CD tracks `main` and deploys nothing on release tags, while Image Updater writes image digests onto Application `devops`. On 2026-11-13 the owner decided that after the repository cutover (`#5134`), one Renovate group pins the devops source, the prometheus `values` source, the dashboards `?ref=`, and the image tags together to one release tag so manifests and images move together, while keeping Image Updater's `argocd` digest write-back unchanged. `#5135` records that policy in an ADR; `#6582` implements the homelab grouped Renovate bump after cutover, and `#7141` moves `workflowtemplate-version.yaml` once the environment freeze ends.

## What Changes

- Add ADR `0040` (`docs/adr/0040-renovate-pins-product-refs-to-release-tags.md`) recording the post-cutover Renovate group pin policy and keeping Image Updater `argocd` digest write-back (`amends: ["0013"]`, `issue: 5135`, `tracker: 5120`).
- Set `amended-by: ["0040"]` and add one dated `Status History` line in `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md` without altering its body hash.
- Regenerate the index table in `docs/adr/README.md` with `uv run devops docs generate`.

## Capabilities

- `adr-records`: Record the post-cutover product pin policy (ADR `0040`) and its amendment link on ADR `0013`.

## Impact

- Documentation (`docs/adr/`); zero runtime, CLI, or `k8s/` manifest edits (`k8s/argocd/image-updater-values.yaml` already retains `updateStrategy: digest` and no `writeBackConfig`).

## Feasibility

Verified `docs/adr/` next free index is `0040`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md` holds `body-hash: 925b8bc4bfb68188c23ad6382749a15c83793ac24e662e45e8bd2975cb8dd1d5`, `k8s/argocd/image-updater-values.yaml` keeps `updateStrategy: digest` with no `writeBackConfig`, and `tests/invariants/test_adr_records.py` validates both records and the regenerated `docs/adr/README.md` index.

## Existing Tool Considered

Renovate (`renovatebot/renovate`, AGPL-3.0, maintained; `alternatives.verdict: in-use`) handles the grouped pin bump in `dan-petty/homelab` (`#6582`), while `#5135` writes only the architectural decision record (`0040`) and regenerates the ADR index using `uv run devops docs generate`.
