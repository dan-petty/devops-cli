# Proposal: #7425

## Why

dan-petty/homelab#552 (merged 2026-11-27, owner decision of the same day) removed the sync option `Prune=confirm` from each Argo CD Application of the homelab, `devops` included. Argo CD now prunes with no approval, and `make k8s-parity` of homelab guards the data objects. Two texts of this repository still describe the confirmation (#7425).

## What Changes

- `k8s/devops/valkey-roadmap/kustomization.yaml`: remove the comment that says Application `devops` waits for a confirmation before each prune, and the generator annotation `Prune=true` that served only that wait.
- `docs/HOMELAB_REPO_SWITCH.md`, step 13: one paragraph says that the Applications prune with no confirmation since dan-petty/homelab#552.

## Capabilities

None: a comment, an annotation with no effect, and a document (`skip_specs: true`).

## Impact

- `kustomize build k8s/devops/valkey-roadmap` gives the same ConfigMap name, `valkey-roadmap-b8gtgcg5t6`, so no pod restarts. The live ConfigMap loses the annotation.
- The change fits one pull request.

## Feasibility

- `kustomize build k8s/devops/valkey-roadmap` before and after the change names `valkey-roadmap-b8gtgcg5t6`: the hash covers the data, not the annotations.
- On 2026-11-27 after the sync of homelab#552, no live Application sets `Prune=confirm` (`kubectl -n argocd get applications -o json`).

## Existing Tool Considered

No tool: a text change.
