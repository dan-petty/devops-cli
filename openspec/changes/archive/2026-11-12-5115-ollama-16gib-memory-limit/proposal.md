# Proposal: #5115 give the ollama-16gib tier a memory limit

## Why

Closes #5115. The container `ollama` of the DaemonSet `ollama-16gib` requests `8Gi` of memory and has no memory limit. Its node now has 16 GiB of memory, not 64 GiB. The tier serves nothing (`k8s/README.md`, GPU Placement), but a DaemonSet pod runs on a cordoned node too. A model load that goes straight to the tier, past the gateway, can take all of the free memory of the node, because no limit stops the container.

## What Changes

- `k8s/llm/profiles/ollama-profiles.yaml`: the container `ollama` of `ollama-16gib` gets a memory limit of `8Gi`, equal to its request. The CPU request stays `3000m`, with no CPU limit. The header comment gives the reason.
- `k8s/README.md`, GPU Placement: the paragraph on `ollama-16gib` states the limit and its reason.
- A manifest is observable, so the change has a spec delta: it adds a requirement to `workload-resource-limits`.

The change fits one pull request.

## Capabilities

- `workload-resource-limits`: ADDED "The 16 GiB Ollama tier limits its memory to its request".

## Impact

- The kernel stops the container, not the node, when the tier uses more than `8Gi`. A model that needs more host memory than `8Gi` does not load on this tier.
- The memory limits of all pods on the node add up to about 10 GiB (`8Gi` plus 768Mi, 768Mi, 256Mi and 256Mi of the DaemonSets of monitoring and GPU discovery). That is below the 13 GiB of allocatable memory that the node has after the system reservation of the homelab repository (dan-petty/homelab pull request 19).
- After the merge, Argo CD rolls the DaemonSet. The pod on the cordoned node restarts with the limit.

## Feasibility

- `kubectl get node hawk` (server v1.37.2+k3s1, read only, 2026-11-12): memory capacity 16240676Ki (15.5 GiB), allocatable equal to capacity. The homelab change sets `system-reserved` 1Gi, `kube-reserved` 1Gi and `eviction-hard` `memory.available<500Mi` on this node, so allocatable becomes 13631524Ki (13.0 GiB).
- `kubectl top pod -n llm` (2026-11-12): `ollama-16gib` uses 283Mi with no model loaded. `ollama-64gib` uses 6602Mi with `qwen3.8:27b` loaded, under its own `12Gi` limit. So one model load fits a limit of `8Gi`.
- `kubectl describe node hawk`: the pods on the node request 9010Mi of memory. The limit adds no request, so the pod still fits the new allocatable.
- Kubernetes "Resource Management for Pods and Containers" (https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/): a container that uses more memory than its limit becomes a candidate for termination by the kernel OOM killer.

## Existing Tool Considered

The change uses the Kubernetes container memory limit and builds nothing. It deletes no internal code.
