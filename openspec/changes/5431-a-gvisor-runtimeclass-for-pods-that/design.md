# Design

## Decisions

- **The root kustomization holds the class.** A RuntimeClass is cluster-scoped and belongs to the cluster, not to one stack. The root kustomization already holds the namespaces and the LimitRange of `mattermost-operator`. Argo CD's `base` Application syncs it, and the `homelab` project admits every cluster-scoped kind. `devops k8s deploy-stack` applies the root kustomization first, so a cluster with no Argo CD also gets the class.
- **The class selects nodes by a label.** `scheduling.nodeSelector` `node-restriction.kubernetes.io/gvisor: "true"` sends each pod of the class to a node that runs `runsc`. The infra repository sets the label last, after it installs `runsc` and restarts the node service, so the label means that `runsc` works on the node. The key is under `node-restriction.kubernetes.io/`: the `NodeRestriction` admission plugin of k3s stops a kubelet from setting it, so only an admin sets it, and a compromised node cannot label itself to attract the pods of the class. The project prefix of the `llm.devops.io/*` labels has no such guard.
- **The class has no tolerations.** No node of the cluster has a taint for gVisor, and a toleration would let a pod of the class onto a node that a person keeps for other work.
- **The class has no `overhead` yet.** `overhead.podFixed` comes from the measurement of `runc` against `runsc` in #5434, and no workload uses the class before it. A guessed value would hide the real cost of the sandbox from the scheduler.
- **The ADR line is "Fact out of date".** ADR 0018 already allows a later gVisor RuntimeClass, so the owner decision of 2026-11-13 changes no decision of the record. Only the fact in Considered Options, "the cluster declares no RuntimeClass for `runsc`", becomes wrong.

## Rejected alternatives

- **Let k3s find `runsc` by itself.** The k3s documentation (<https://docs.k3s.io/advanced>) lists the runtimes that k3s finds on a node, and `runsc` is not one of them. The live cluster has 10 RuntimeClasses and none for `runsc`.
- **A class with no `scheduling`.** `kubectl explain runtimeclass.scheduling` says that a nil `scheduling` means that every node supports the class. Then a pod of the class can land on a node with no `runsc`, and its sandbox fails to start there.
- **The product base `k8s/devops`.** The product base ships with devops-cli to any cluster. The class depends on the setup of the nodes of one cluster, which the infra repository owns, so it belongs in the environment tree.
- **The `kubernetes-sigs/agent-sandbox` controller now.** ADR 0018 names it as the other option, and #2695 owns its measurement. A RuntimeClass is the smaller step and the controller can use it later.
