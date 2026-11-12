# Proposal: #4996 delete the CoreDNS files that k3s never applies

## Why

Closes #4996. Git says that CoreDNS runs with a 200m CPU and 384Mi memory limit. The live Deployment is the k3s packaged manifest, with 1 replica, a 170Mi memory limit and no CPU limit. No command, kustomization or Argo CD Application applies the files in `k8s/coredns/`, and the HelmChartConfig has no HelmChart to change. A reader of git gets the wrong limit. This item is rank 6 of the cluster integration plan #4989.

## What Changes

- Delete `k8s/coredns/helmchartconfig.yaml`, `k8s/coredns/deployment-patch.yaml` and `k8s/coredns/values.yaml`.
- Remove the entry `k8s/coredns/deployment-patch.yaml:Deployment/coredns` from `_TOKEN_EXCEPTIONS` in `tests/invariants/test_k8s_manifests.py`, and the assertions of the 384Mi values from `tests/commands/k8s/test_k8s.py`.
- `k8s/README.md` says that k3s, not git, holds CoreDNS, gives the live replicas, requests and limits, and says that only the owner changes them. It removes the note that `k8s/coredns/` is managed outside Argo CD, and the CoreDNS item of the token exceptions.
- The change deletes files that the cluster never read, and edits tests and a document. The live cluster does not change, so the change has no spec delta (`skip_specs: true`).

## Capabilities

None. No requirement in `openspec/specs/` names the deleted files or the CoreDNS size.

## Impact

- The cluster does not change: k3s keeps CoreDNS at its packaged values.
- A reader of git sees no CoreDNS size that the cluster does not use.
- The option to run CoreDNS from its Helm chart with 2 replicas and a larger limit stays an owner decision on #4989. It is a change of the k3s server (`--disable=coredns`, or a `.skip` file for the packaged manifest).
- No alert reads the memory of CoreDNS. #4993 asks for an alert on each container near its memory limit.

## Feasibility

- `kubectl -n kube-system get deployment coredns` (server v1.37.2+k3s1, image `rancher/mirrored-coredns-coredns:1.14.7`) shows 1 replica, requests 100m CPU and 70Mi memory, and a 170Mi memory limit. Its annotation `objectset.rio.cattle.io/owner-gvk` is `k3s.cattle.io/v1, Kind=Addon` with owner `coredns`.
- `kubectl -n kube-system get addon coredns` names the source `coredns.yaml` in the k3s server manifests folder.
- `kubectl -n kube-system get helmchart,helmchartconfig` lists only the HelmChart `gateway-api-crd` and no HelmChartConfig. Thus nothing applied `k8s/coredns/helmchartconfig.yaml`.
- No Argo CD Application names `k8s/coredns` (`kubectl get applications -A -o json`), and no kustomization, Makefile target or module under `src/` reads the folder (`git grep`).
- The k3s document of packaged components (https://docs.k3s.io/installation/packaged-components) says that k3s deploys `coredns` as an AddOn from the manifests folder, and writes the files again whenever it starts. The k3s Helm document (https://docs.k3s.io/add-ons/helm) says that a HelmChartConfig customizes "packaged components that are deployed as HelmCharts (such as Traefik)", and must match the name and namespace of its HelmChart.

## Existing Tool Considered

- k3s packaged components and its HelmChartConfig resource are the open tools that size CoreDNS. The change keeps the k3s packaged manifest and builds nothing.
- The change deletes the three files in `k8s/coredns/`, one exception entry and the CoreDNS assertions of `test_k8s_workload_resource_limits_and_probes`.
