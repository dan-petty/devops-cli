---
status: proposed
date: 2026-11-25
decision-makers: [owner]
issue: 5135
tracker: 5120
amends: ["0013"]
---

# Renovate pins product refs to release tags after cutover

## Context and Problem Statement

Today `k8s/devops` changes roll through Argo CD on `main` while images roll at release: Application `devops` tracks `targetRevision: main`, Application `prometheus` reads `k8s/devops/monitoring/prometheus-rules-values.yaml` from `main`, the homelab dashboards kustomization tracks `?ref=`, and Argo CD Image Updater writes `service:latest@sha256:<digest>` onto Application `devops`. [ADR 0013](0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md) records that Argo CD tracks `main` and that tags deploy nothing. On 2026-11-13 the owner decided that after the repository cutover ([#5134](https://github.com/dan-petty/devops-cli/issues/5134)), one Renovate group pins all four items to one release tag so manifests and images move in the same sync.

## Decision Drivers

- Avoid skew between `k8s/devops` manifests and published container images (`#4036`).
- Move `targetRevision` of Application `devops`, the `values` ref of Application `prometheus`, the dashboards ref, and the product image tags in one sync.
- Keep all four items on `main` until the repository cutover finishes.
- Keep Argo CD Image Updater `argocd` write-back (`updateStrategy: digest`, `forceUpdate: true`) unless the owner changes it.

## Considered Options

- **One Renovate group after the cutover pins all four items to one release tag**: chosen.
- **Pin the manifests now before the cutover**: rejected, because pinning now blocks the cutover path (`#5120`).
- **Pin only the manifests at a release tag**: rejected, because fast releases cause manifest and image skew (`#4036`).
- **Bump each ref and image tag in separate pull requests**: rejected, because separate pull requests let the four refs drift apart.

## Decision Outcome

Chosen option: "One Renovate group after the cutover pins all four items to one release tag", because it keeps manifests, dashboards, values, and image tags on one release without skew.

- Until the cutover (`#5134`) completes, `targetRevision` of Application `devops`, the `values` source of Application `prometheus`, the dashboards `?ref=`, and the product image tags continue to track `main`.
- After the cutover, one Renovate group in `dan-petty/homelab` (`#6582`) pins and bumps all four items together to the same devops-cli release tag, amending ADR 0013's rule that Argo CD tracks `main` and deploys nothing on tags.
- Argo CD Image Updater keeps its `argocd` write-back on Application `devops` with `updateStrategy: digest`, `forceUpdate: true`, and no `writeBackConfig` in `k8s/argocd/image-updater-values.yaml`; only the owner can change that setting.
- Moving `workflowtemplate-version.yaml` into the product base waits in `#7141` until the environment freeze ends.

### Consequences

- Good, because manifests and images move together in one Renovate pull request and one Argo CD sync after the cutover.
- Good, because Image Updater keeps digest freshness without adding git write-back conflicts.
- Bad, because `dan-petty/homelab` tracks the pinned release tag instead of immediate `main` commits once the pin runs.

### Confirmation

- `tests/invariants/test_adr_records.py` checks this record, ADR 0013's `amended-by` and `Status History`, and the generated index row in `docs/adr/README.md`.
- `uv run devops ci --check --only k8s` confirms that `k8s/argocd/image-updater-values.yaml` keeps digest write-back with no `writeBackConfig`, and `#6582` checks that the first grouped Renovate bump matches the `k8s/devops` release diff.

## More Information

- Issue [#5135](https://github.com/dan-petty/devops-cli/issues/5135), tracker [#5120](https://github.com/dan-petty/devops-cli/issues/5120), deferred items [#6582](https://github.com/dan-petty/devops-cli/issues/6582) and [#7141](https://github.com/dan-petty/devops-cli/issues/7141).
- [ADR 0013](0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md).
- Change: `openspec/changes/archive/2026-11-25-5135-pin-product-base-adr/`.
