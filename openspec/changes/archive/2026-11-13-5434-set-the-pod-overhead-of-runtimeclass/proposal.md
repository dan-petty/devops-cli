# Proposal: #5434

## Why

The issue #5434 measures `runsc` against `runc` for RuntimeClass `gvisor` (#5431) and sets `overhead.podFixed` of the class from the measurement. The measurement ran on 2026-11-13, and [its result](https://github.com/dan-petty/devops-cli/issues/5434#issuecomment-6860621985) is on the issue. The class has no `overhead` now. So the scheduler, the kubelet and a ResourceQuota do not count the memory of the gVisor Sentry and the gofer. A node can then take more pods of the class than its memory holds. This change sets the measured overhead and closes #5434.

## What Changes

- `k8s/runtimeclass-gvisor.yaml` sets `overhead.podFixed` to memory `16Mi`: the measured 15.1 MiB of fixed memory for each pod, rounded up. The measurement found no CPU overhead, so the class has no `cpu` key. The header line that says that no workload uses the class before #5434 sets the overhead goes. Header lines that name the source of the value replace it.
- `tests/invariants/test_k8s_argocd_apps.py` pins the `overhead` of the class to exactly `podFixed: {memory: 16Mi}`.
- `k8s/README.md`, section "gVisor Runtime": the bullet "Use" gives the kernel version that the pinned `runsc` reports (`4.19.0-gvisor`; an older `runsc` printed `4.4.0`). The bullet "Limits" gives the measured result with a link to the comment of #5434. A new bullet "Overhead" gives the value `16Mi`, what counts it, and where the measurement ran.
- A manifest is behavior that a consumer observes, so the change carries a spec delta: one ADDED requirement in `k8s-gvisor-runtime`.
- No workload sets `runtimeClassName: gvisor` in this change. The first workload of the class is a sandbox entry under the policy of #5447, and the owner approves it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-gvisor-runtime`: ADDED requirement "RuntimeClass gvisor declares the measured pod overhead".

## Impact

- Manifests: `k8s/runtimeclass-gvisor.yaml`
- Docs: `k8s/README.md`
- Tests: `tests/invariants/test_k8s_argocd_apps.py`
- Cluster: Argo CD's `base` Application changes the one cluster-scoped RuntimeClass in place. No pod restarts: no pod uses the class, and admission adds the overhead to a pod only when the pod is created. A later pod of the class gets 16Mi more in its scheduling request, its pod cgroup and the quota of its namespace.

## Feasibility

- The measurement of 2026-11-13 (comment on #5434) ran interleaved `runc` and `runsc` Jobs of the runner image on the labelled node. A canary under `runsc` reported kernel `4.19.0-gvisor` with `runsc` release 20261109.0. CPU work had no overhead, file work was 1.44 times slower, and headless Chromium worked (1.4 s against 0.7 s). The pod working set minus the RSS was -7.7 MiB under `runc` and +7.4 MiB under `runsc`. So the fixed overhead is 15.1 MiB for each pod. A CPU limit of 500m held (2.6 times slower), and an allocation past a memory limit of 224 MiB ended in `OOMKilled`. The start time did not change.
- `kubectl` on 2026-11-13: the live RuntimeClass `gvisor` has handler `runsc`, the node selector `node-restriction.kubernetes.io/gvisor: "true"` and no `overhead`. One node has the label. It is an agent node, not the control-plane node, with runtime `containerd://2.3.7-k3s1` and kubelet `v1.37.2+k3s1`. No pod sets `runtimeClassName: gvisor` (count 0 from `kubectl get pods -A`).
- `kubectl explain runtimeclass.overhead.podFixed` (API `node.k8s.io/v1`): the field is a `map[string]Quantity`.
- `kubectl apply --dry-run=server -f k8s/runtimeclass-gvisor.yaml` on the branch gives `runtimeclass.node.k8s.io/gvisor configured (server dry run)`. So the API server takes the change of the existing class in place. `kubectl diff -f k8s/runtimeclass-gvisor.yaml` shows only the `overhead` block and the Argo CD tracking annotation, which Argo CD keeps at sync.
- `kubectl kustomize k8s` at `origin/main` and at the branch: the only difference is the three lines of the `overhead` block of RuntimeClass `gvisor`.
- Kubernetes documentation, Pod Overhead (<https://kubernetes.io/docs/concepts/scheduling-eviction/pod-overhead/>): at admission, the RuntimeClass admission controller adds the `overhead` of the class to the PodSpec. The scheduler counts it with the container requests. The kubelet adds it when it sizes the pod cgroup and when it ranks pods for eviction. A ResourceQuota counts it too.

## Existing Tool Considered

The Kubernetes RuntimeClass API (`node.k8s.io/v1`, field `overhead.podFixed`) and the Pod Overhead feature cover the need. This change sets one field, adds one test and changes one document. It builds no code, and it deletes no internal code.
