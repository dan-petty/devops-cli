# Proposal: #7257

## Why
After step 14 of the switch (#5134), the infra repo holds the hosts of `devops`, `ingress` and `mattermost` as patches of their Application files. `deploy-stack` still writes the same field from `config.yaml`, so two sources write it.

## What Changes
`deploy-stack` patches no Application and needs no domain on a cluster that Argo CD manages. The option `--argocd-revision` and `k8s/argocd_overrides.py` go. The Argo CD gate keeps the rule on the placeholder host fields, which moves into `argocd_gate.py`.

## Capabilities
- `gitops-host-overrides`: the deploy-time overrides go, and the gate rule stays.

## Impact
A person changes a host in the infra repo. A deploy without Argo CD still renders the configured domain.

## Feasibility
Confirmed on 2026-11-25: dan-petty/homelab#242 holds each live patch list in its Application file, and each whole spec equals the live spec except the image digest.

## Existing Tool Considered
Kustomize patches in the Application files of the infra repo, which Argo CD applies, replace the code.
