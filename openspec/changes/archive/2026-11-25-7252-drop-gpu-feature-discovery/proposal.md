# Proposal: #7252

## Why
`devops k8s deploy-stack` applies DaemonSet `gpu-feature-discovery`, which runs privileged on every node and labels nothing: no cluster of this project runs Node Feature Discovery, and the container finds no GPU. Since v0.20.2 it also exits 1.

## What Changes
`devops k8s deploy-stack` and `teardown-stack` of the stacks `infra` and `all` no longer take the folder `gpu-feature-discovery` of the environment tree. The folder stays in this repository until step 17 of #5134 deletes the environment files. The homelab repository removes its Application and folder.

## Capabilities
- `k8s-helm-deploy`: the kustomizations of a native infra deploy.

## Impact
A cluster that an earlier native deploy gave the DaemonSet keeps it until a person deletes it. The GPU labels of the nodes do not change.

## Feasibility
Checked on 2026-11-25 on the homelab: no Node Feature Discovery workload or CRD; v0.16.2 logs `Unsupported strategy detected: auto using empty manager`; the feature file holds no GPU data; no node has a label that only this DaemonSet would set, and `kubectl label` set each `nvidia.com/*` label.

## Existing Tool Considered
Node Feature Discovery would read the file. It adds a component to replace labels that work, so it stays a separate item.
