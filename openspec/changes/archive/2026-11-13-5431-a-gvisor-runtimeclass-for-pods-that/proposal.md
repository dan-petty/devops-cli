# Proposal: #5431

## Why

The issue #5431 adds a gVisor RuntimeClass for pods that run untrusted code. The jobs of the Service run code that a model writes: the implement runner, the run Job of the planner (#4003), the in-cluster browser (#5356) and crawl4ai. The boundary of each is the container of the pod. ADR 0018 accepts that boundary and says that a defect of the host kernel stays a risk, and that a gVisor RuntimeClass can close it later with no change of the tool. The owner decided on 2026-11-13 to use gVisor (`runsc`). The cluster declares no RuntimeClass for `runsc` today, and k3s does not find `runsc` on a node by itself. So the environment tree must declare the class.

## What Changes

- `k8s/runtimeclass-gvisor.yaml` declares RuntimeClass `gvisor` (`node.k8s.io/v1`) with handler `runsc` and `scheduling.nodeSelector` `node-restriction.kubernetes.io/gvisor: "true"`, and no tolerations. The key is under `node-restriction.kubernetes.io/`, so a kubelet cannot set it on its own node.
- The root kustomization `k8s/kustomization.yaml` lists the file. Argo CD's `base` Application syncs that path on the homelab, and `devops k8s deploy-stack` applies it first on a cluster with no Argo CD. On minikube no node has the label, so the class does nothing there.
- `tests/invariants/test_k8s_argocd_apps.py` pins the object and its place in the root kustomization.
- `k8s/README.md` gets the section "gVisor Runtime" and a line in the directory structure. The section names the node label, the infra repository that installs `runsc`, the use of `runtimeClassName: gvisor`, and two limits: the seccomp profile of the pod is not loaded under `runsc`, and the measurement of #5434 must prove the CPU and memory limits and set `overhead.podFixed` before a workload uses the class.
- ADR 0018 gets one Status History line, because its fact "the cluster declares no RuntimeClass for `runsc`" becomes wrong. The body of the record does not change.
- No workload sets `runtimeClassName: gvisor` in this change.
- A manifest is behavior that a consumer observes, so the change carries a spec delta. The change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-gvisor-runtime`: The environment tree declares RuntimeClass gvisor for the runsc nodes

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/runtimeclass-gvisor.yaml`, `k8s/kustomization.yaml`
- Docs: `k8s/README.md`, `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` (Status History only)
- Tests: `tests/invariants/test_k8s_argocd_apps.py`
- Cluster: one cluster-scoped object. Until a node has the label, a pod of the class stays Pending. The infra repository installs `runsc` and sets the label in its own pull request. The two pull requests can merge in either order.

## Feasibility

- The cluster, read with `kubectl` on 2026-11-13: 4 nodes with kubelet `v1.37.2+k3s1` and runtime `containerd://2.3.7-k3s1`. The cluster has 10 RuntimeClasses (`crun`, `lunatic`, `nvidia`, `nvidia-experimental`, `slight`, `spin`, `wasmedge`, `wasmer`, `wasmtime`, `wws`) and none with handler `runsc`. `kubectl get nodes -l node-restriction.kubernetes.io/gvisor=true` gives no node.
- `kubectl explain runtimeclass.scheduling` (API `node.k8s.io/v1`): admission merges `nodeSelector` into the node selector of the pod, and a nil `scheduling` means that every node supports the class. `kubectl apply --dry-run=server -f k8s/runtimeclass-gvisor.yaml` gives `runtimeclass.node.k8s.io/gvisor created (server dry run)`.
- `kubectl kustomize k8s` renders one RuntimeClass `gvisor` with handler `runsc` and the node selector.
- k3s documentation (<https://docs.k3s.io/advanced>): with containerd 2.x, k3s reads `config-v3.toml.tmpl`, a template extends the defaults with `{{ template "base" . }}`, and a runtime goes under `plugins.'io.containerd.cri.v1.runtime'.containerd.runtimes.<name>`. The list of runtimes that k3s finds by itself does not include `runsc`. `--node-label` applies only when a node registers, so the infra repository sets the label with `kubectl label`.
- gVisor documentation (<https://gvisor.dev/docs/user_guide/containerd/quick_start/>): runtime type `io.containerd.runsc.v1`, RuntimeClass `gvisor`, handler `runsc`. The install guide gives the apt repository, its date suites and the signing key.
- `runsc/config/flags.go` at tag `release-20261109.0`: `oci-seccomp` defaults to false, `systemd-cgroup` defaults to false and is experimental, and the platform defaults to `systrap`. So the seccomp profile of a pod is not loaded under `runsc`, and the infra repository sets `systemd-cgroup` because the kubelet uses the systemd cgroup driver.
- containerd CRI documentation (<https://containerd.io/docs/main/cri/config/>): for a shim runtime such as `io.containerd.runsc.v1`, containerd reads the cgroup driver from the `ConfigPath` file.
- Open gVisor issue #13777 reports pod CPU and memory limits that do not hold under containerd 2.2 with `systemd-cgroup`. So `k8s/README.md` asks for the measurement of #5434 before a workload uses the class. #5434 is a sub-issue of #2695 and holds the measurement plan.
- Kubernetes documentation (<https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#node-isolation-restriction>): the `NodeRestriction` admission plugin stops a kubelet from setting or changing a label under `node-restriction.kubernetes.io/`, and labels for node isolation must use such keys, so a compromised node cannot label itself to attract workloads. The k3s server source (`pkg/daemons/control/server.go`) sets `enable-admission-plugins=NodeRestriction` and the `Node` authorizer.
- gVisor documentation (<https://gvisor.dev/docs/architecture_guide/security/>): the Sentry makes a minimal set of host system calls. So the host kernel surface of a pod is smaller, but not zero.
- `docs/adr/README.md` admits the line form `YYYY-MM-DD: Fact out of date: <what> (#N).`, 30 words or fewer after the date, and `tests/invariants/test_adr_records.py` keeps the `body-hash` of ADR 0018.

## Existing Tool Considered

gVisor (`runsc`, Apache-2.0) and the Kubernetes RuntimeClass API (`node.k8s.io/v1`) cover the need. This change adds one manifest, one test and documents, and it builds no code. The change deletes no internal code. The `kubernetes-sigs/agent-sandbox` controller is the other option of ADR 0018, and #2695 owns its measurement.
