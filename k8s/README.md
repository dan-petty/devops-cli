# k8s/ — The Product Base and the Cluster Commands

**The environment of the cluster lives only in the `k8s/` folder of dan-petty/homelab.** That folder holds what one cluster runs: the Argo CD Applications, the values of the charts, the manifests of the stacks, the overlays, the dashboards of the cluster and its runbooks. Read, edit and apply an environment file there. devops-cli holds no copy of it, and the `k8s` row of `devops ci` refuses a tracked file under `k8s/` that is not in `k8s/devops` and is not Markdown (`tests/gate/k8s_checks/product_tree.py`).

This folder holds `k8s/devops/`, the product base that devops-cli ships. This document tells what the cluster commands of devops-cli do, and the decisions about the product base. The [Kubernetes guideline](../docs/guidelines/kubernetes.md) sets the performance targets of a cluster and the method to tune the requests, the limits, the placement and the runtimes.

A command that reads the environment tree (`deploy-stack`, `teardown-stack`, `push-secrets`, `bootstrap-mattermost`, `catalog`, `image-pins` and `lint` with no target, `ollama prune`, `devops grafana dashboards` and `devops ai gateway render`) takes its root from `--k8s-dir`, else from the project profile fact `kubernetes.dir` of the repository of the current folder, else from the one entry of `infra.repos` whose checkout gives `kubernetes.dir`. This repository declares no `kubernetes.dir`. So from a checkout of devops-cli, give `--k8s-dir <homelab-checkout>/k8s`, or add the checkout of dan-petty/homelab to `infra.repos`. `devops k8s bootstrap` takes the tree as `--dir`. `devops k8s check-deprecated`, `devops argo cd apps bootstrap-gitops`, `devops argo gitops drift` and `watch`, and `devops config set <key> --generate` for a key of the environment have no `--k8s-dir`: they read the tree of `infra.repos`, or the path of their own argument or option (the target, `--root-app`, `--path`). Keep that checkout at the current `main`. A command that needs a path that the tree does not hold fails, and its message names the path. `deploy-stack` and `teardown-stack` read the product base from `--product-dir`, else from `k8s/devops` of the repository of the current folder. A path in the environment tree is relative to its root, such as `llm/gateway/config.yaml`.

## Stacks Overview

The stacks are the units of `deploy-stack` and `teardown-stack`. The environment tree holds the manifests, the values and the versions of their components.

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Argo Workflows controller, Grafana k8s-monitoring (Alloy + kube-state-metrics + node-exporter), Prometheus server, Grafana, Alertmanager, Grafana Pyroscope, NVIDIA DCGM Exporter, OpenTelemetry Collector, Grafana Tempo, CloudNativePG operator, cert-manager and the Barman Cloud plugin, the SeaweedFS operator and object store | `argocd`, `argo-workflows`, `monitoring`, `otel`, `cnpg-system`, `cert-manager`, `object-store` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus), `4040` (Pyroscope), `3200` (Tempo), `8333` (S3, in the cluster) |
| **`llm`** | Ollama (per-VRAM-tier DaemonSets), LLM Gateway (LiteLLM) with its CloudNativePG database, Open-WebUI, Qdrant Vector DB, Valkey Cache | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
| **`logging`** | Loki (pod and journal logs shipped by the `infra` stack's Alloy `alloy-logs` DaemonSet) | `logging` | `3100` (Loki) |
| **`gitea`** | Gitea: the internal forge and container registry ([Gitea](#gitea)) | `gitea` | `3000` (Gitea HTTP, in the cluster) |
| **`chat`** | Mattermost Team Edition on CloudNativePG ([Mattermost](#mattermost)) | `mattermost`, `mattermost-operator` | `8065` (Mattermost HTTP, in the cluster) |
| **`all`** | All components from the stacks above, and the `devops` stack ([docs/CLUSTER.md](../docs/CLUSTER.md)) | `argocd`, `argo-workflows`, `monitoring`, `otel`, `llm`, `logging`, `gitea`, `devops`, `mattermost`, `cnpg-system`, `mattermost-operator`, `cert-manager`, `object-store` | All ports above |

Register each manifest and post-Helm step that runs in the cluster in `APPLICATIONS_BY_STACK`, `MANIFESTS_BY_STACK` or `POST_HELM_BY_STACK` (`src/devops_cli/commands/k8s/stack_lifecycle.py`), with an Argo CD Application or a path in the environment tree, or a file of the product base in `PRODUCT_MANIFESTS_BY_STACK` or `PRODUCT_POST_HELM_BY_STACK`, with a path in `k8s/devops`, and each Helm release in `HELM_RELEASES_BY_STACK`, so that `devops k8s deploy-stack --stack all` deploys it with the `infra`, `llm`, `logging`, `devops`, `gitea` and `chat` stacks. deploy-stack applies a file of `MANIFESTS_BY_STACK` with `kubectl apply -f` and a kustomization directory with `kubectl apply -k`. For each Application of `APPLICATIONS_BY_STACK`, deploy-stack builds each path source with Kustomize, as Argo CD builds it, and applies the build with `kubectl apply -f -` before the charts; `teardown-stack` deletes the build. So a component or a base of another repository in the folder of an Application gets to a cluster without Argo CD. A source of another repository is fetched at its `targetRevision`. The dry run of deploy-stack builds each folder of the checkout as a local read and lists the objects of each build in `details.path_sources`. The dry run of teardown-stack lists them in `details.path_source_deletes`, in the order of the deletes. A path source whose `path` goes out of the folder of its repository stops the command, because Argo CD builds no such path. Kustomize fetches a remote base, component or file, so the dry run gives `kubectl kustomize` no route to a host that is not a loopback address: `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` (also in lower case) point to the closed port `127.0.0.1:9`, `NO_PROXY` is empty, and `GIT_ALLOW_PROTOCOL=file` lets git clone only local repositories. A download of Go and a clone of git then fail at once. Go sends a request to `localhost` or to a loopback address with no proxy, and no environment key changes this. So the dry run downloads each http or https URL of a loopback address: a file, and also the URL of a remote base, which Kustomize first loads as a file. Such a request is not a read of the checkout: it can reach a `kubectl port-forward` or a tunnel to a cluster. A git clone from a loopback address still fails. When a build fails, its objects are `null`, `details.kustomize_fetches` gives the error of kubectl as one line under the key of the build, and the dry run goes on. The real run builds with the normal environment. A path of `MANIFESTS_BY_STACK` stays only where the build of its Application holds objects that the path does not hold, such as the post-Helm objects of the Application `llm`. A row of `HELM_RELEASES_BY_STACK` gives the name, the chart and the namespace of a release. deploy-stack takes the chart version and the values files of the release from the chart source of the Argo CD Application of the same name: the `targetRevision`, and the files of `helm.valueFiles` in their order. A values file of another repository, such as `$infra/helm/<chart>/values.yaml`, is fetched at the `targetRevision` of its source before the deploy touches the cluster; the dry run lists the fetch in `details.source_fetches`.

### valkey-roadmap

`valkey-roadmap` (`devops/valkey-roadmap/`, namespace `devops`) holds the shared state of the roadmap jobs, with the brain index as its first data ([ADR 0021](../docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md), section 3). It is a part of the product base, so Application `devops` deploys it. The folder builds the shared Valkey base of dan-petty/infra with its components `valkey-persistence`, `valkey-exporter` and `valkey-acl` at a release tag, which Renovate updates. It keeps its data in an append-only file on a 2Gi `local-path` claim, and at its bound of 128 MiB it refuses a write and evicts no key. Its exporter gives the series that the alerts `ValkeyCacheErrors` and `ValkeyMemoryNearBound` of the environment read. Alloy of the environment finds it by annotation autodiscovery (job `valkey`). Its user `default` is off, and each client sends an ACL user of Secret `devops/valkey-roadmap-auth` (see Cluster Secrets). The roadmap Service pod is the one client: it has the label `valkey-client: "true"`, the password of the user `brain` and an egress rule to the store in `roadmap-service-egress`, and its alternatives row writes the brain index (#4676). [valkey-roadmap](../docs/CLUSTER.md#valkey-roadmap) gives its users, its policies and its checks.

## Prerequisites

- A cluster: the k3s homelab, or minikube (`minikube status`, or started by `devops devcontainer post-start`).
- kubectl and helm on PATH, from the devtools image. `devops k8s doctor` reads the version of kubectl.
- A Kubernetes context: the CLI uses `$KUBECONFIG`, or `~/.kube/config`.
- A checkout of dan-petty/homelab at the current `main`, for each command that reads the environment tree.
- A storage layer that serves the StorageClass `local-path`, which the claims of the stacks use. On the homelab, it comes from dan-petty/homelab. On minikube, the class comes from the `storage-provisioner-rancher` addon: `devops` starts minikube with `--addons=storage-provisioner-rancher`. On a minikube that already runs, run `minikube addons enable storage-provisioner-rancher` one time, or the claims that name `local-path` stay `Pending`.

## Quick Start

```bash
export KUBECONFIG=$HOME/.kube/config

# Deploy the default infrastructure stack
devops k8s deploy-stack --k8s-dir <homelab-checkout>/k8s

# Deploy the LLM stack
devops k8s deploy-stack --stack llm --k8s-dir <homelab-checkout>/k8s

# Deploy all stacks
devops k8s deploy-stack --stack all --k8s-dir <homelab-checkout>/k8s
```

The minikube cluster of the devcontainer uses the same environment tree, so these commands need the homelab checkout there too. The addresses of the services and the steps for each stack are in `k8s/README.md` of dan-petty/homelab.

## Port Forwarding & Automated Configuration

```bash
# Forward ports and automatically detect URLs
devops k8s port-forward --stack infra
devops k8s port-forward --stack llm
devops k8s port-forward --stack all

# Auto-detect URLs and persist to devops config
devops k8s configure-urls --stack infra
devops k8s configure-urls --stack llm
```

A NetworkPolicy of the environment can limit who reaches a Service. How each way to reach a stack gets through:

- `devops k8s port-forward` works wherever the pods run: `kubectl port-forward` enters the pod's own network namespace, and no policy applies.
- `--addressing fqdn` goes through the ingress controller.
- `--addressing proxy` writes `k8s://` addresses that the API server proxies from the control-plane node's host network. kube-router admits host-network traffic only to pods on the same node, so in a namespace behind a perimeter, a Service answers this way only while its pod runs on the control-plane node. So `configure-urls --addressing proxy` sends one GET through the API server for each address. It writes only the addresses that the Service answers. When the API server cannot dial the Service, it writes nothing for that key and names `fqdn` and port-forward.

## NetworkPolicy

Each NetworkPolicy of `k8s/devops` has one type. A policy with ingress and egress rules is two policies with the same pod selector: `<name>-ingress` with the type `Ingress` and the ingress rules, and `<name>-egress` with the type `Egress` and the egress rules. The network policy controller of the homelab, kube-router, does not apply the ingress rules of a policy with both types to traffic that an egress rule of the same policy allows, when the policy selects the source pod and the destination pod (#6707, #6708). The `k8s` row of `devops ci` refuses each policy whose types hold `Ingress` and `Egress` (`dual_type_problems` in `tests/gate/k8s_checks/network_policies.py`). It reads the types as the API server sets them: `policyTypes` as written; with no `policyTypes`, `Ingress`, and `Egress` when the policy has an egress rule.

## Argo Workflows

Each Argo object of `k8s/devops` uses the fields that the Argo Workflows controller v4 reads: `schedules` on a CronWorkflow, and `mutexes` and `semaphores` in `synchronization`. The controller refuses a CronWorkflow with the singular `schedule` (`SpecError`, `cron workflow must have at least one schedule`), and it does not read the singular `mutex` or `semaphore`. The installed CRDs keep unknown fields, so the API server and Argo CD accept such an object. The `k8s` row of `devops ci` runs `argo lint --offline` on the Argo objects of the render, and fails on each field that the controller does not know (`tests/gate/k8s_checks/argo_workflows.py`, #5289). The `argo` command comes from the devtools image. To run the lint by hand, run `uv run devops ci --check --only k8s`.

## Local-Path Volume Placement

The StorageClasses `local-path` and `fast-nvme` use the local-path provisioner ([Prerequisites](#prerequisites)). It keeps a volume in a directory on one node, and it binds the volume on the node where the first pod of the claim runs (`WaitForFirstConsumer`). The volume then keeps each later pod of the claim on that node. The control-plane node of the homelab has the least free root disk space. So each pod that mounts a claim has this required node affinity:

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: node-role.kubernetes.io/control-plane
              operator: DoesNotExist
```

Kubernetes puts the label `node-role.kubernetes.io/control-plane` on each control-plane node, so the rule needs no label of its own. The affinity has an effect on a new volume and on a moved volume. A bound volume keeps its pod on its node.

Each pod that mounts a claim sets this affinity, in its manifest under `k8s/devops` or in the environment tree. Review holds this rule; no test reads the files (#6060). The environment tree records the pods that still stay on the control-plane node.

### Move a volume to another node

`devops k8s volume move <namespace>/<claim>` copies the data of a claim to a new volume on a worker node, and binds the claim to that volume. The workload stops while the copy runs. Move one volume at a time. The copy is [pv-migrate](https://github.com/utkuozdemir/pv-migrate) (Apache-2.0), which the devtools image installs: the plan refuses a move when `pv-migrate` is not on `PATH`.

```bash
devops k8s volume move monitoring/grafana --plan
devops k8s volume move monitoring/grafana
devops k8s volume move logging/storage-loki-0 --to-node <worker-node>
devops k8s volume move llm/qdrant-storage-qdrant-0 --storage-class longhorn
```

`--plan` only reads, and prints each step with the real names. `--dry-run` makes no request, and prints the requests of a move. Without `--to-node`, the command moves a volume from the control-plane node to the worker node with the most free disk (`node.fs.availableBytes` in the kubelet's `/stats/summary`). A volume on a worker node moves only to the node that `--to-node` names. The command refuses a claim that is not `Bound`, a target on the control-plane node, a StatefulSet that deletes its claims when it scales down (`persistentVolumeClaimRetentionPolicy.whenScaled: Delete`), and the claim `<claim>-move` of an earlier move. It also refuses a paused Application owned by an ApplicationSet unless `spec.ignoreApplicationDifferences` ignores `/spec/syncPolicy`.

The move does these steps, and prints each one:

1. It pauses automated sync from the top down: the root Applications of the setting `argocd.root_applications` (`bootstrap`, `cluster`), then each Application that tracks the claim or the workloads that mount it (Pausing an Application, below). If it did not, self-heal would start the workload again during the copy. A pause does not stop a sync operation that already runs, such as the retry of a sync that failed on the immutable class of the claim, and such an operation can make a deleted claim again from git. So after the pause, and again before it deletes the old claim, the move ends each sync operation of a paused Application that still runs, as `argocd app terminate-op` does, and waits until it is `Failed` (up to 10 minutes). Between two attempts, such an operation has `finishedAt` and still the phase `Running`.
2. It makes the claim `<claim>-move`, with the size of the old claim and its class (or the class that `--storage-class` names).
3. It scales the workloads that mount the claim to zero. It finds them from the volumes of the pod specs, not from labels. It leaves out a pod that has ended (phase `Succeeded` or `Failed`), such as a pod that the shutdown of its node ended: it holds no volume, and a scale to zero does not delete it.
4. It copies the old claim to `<claim>-move` with `pv-migrate --strategies clusterip` (#7498). pv-migrate installs its chart as one Helm release, operation `volume-move-<8 hex digits>`: an sshd pod that mounts the old claim read-only, on the old node, and an rsync Job that mounts `<claim>-move` and pulls the data over SSH through a ClusterIP Service. The values on stdin put the rsync pod on the target node (`nodeSelector`), so local-path binds the new volume there, and give the sshd pod the tolerations of the workload pod and of a cordon. pv-migrate makes an allow-all NetworkPolicy for each of its pods, so a namespace that refuses traffic by default lets the copy pass. rsync (`-a`) keeps the modes, the times and the symbolic links, checks each file that it sends, and tries again up to 10 times. It copies a hard link as a separate file and writes a sparse file in full, so give a larger `--size` when the data then does not fit. pv-migrate refuses a claim that a running pod mounts, and removes its release at the end, also when it fails. Then the move reads the new volume of `<claim>-move`.
5. It sets the two volumes to `Retain`, and ends each sync operation of a paused Application that still runs (step 1).
6. It saves the old claim as a JSON file in `k8s/volume-move/` under the data directory, deletes the pods of the claim that have ended (the claim protection counts them, so the delete of the claim would wait for them), and deletes the old claim. This is the point of no return.
7. It deletes `<claim>-move`, reserves its volume for the claim name (`claimRef`), and makes the claim again from the saved one, with `spec.volumeName` and the class of the new volume. It leaves out the annotation `kubectl.kubernetes.io/last-applied-configuration`, and puts the saved value back after the create. `kubectl create` writes the whole new object, `volumeName` included, into that annotation when the manifest has it. Argo CD then tries to remove `volumeName`, and the API server refuses the change (`spec is immutable after creation`).
8. It scales the workloads back, makes sure that their pods run on the target node (with a class change, that they run on a node that the scheduler selects), and turns on automated sync again: the Application, `cluster`, then `bootstrap`.

Before the point of no return, a failure undoes each change of the move, the last change first. When the run stops pv-migrate (an interrupt, or the bound of one hour), pv-migrate has no time to remove its release, so the undo runs `pv-migrate cleanup <operation> --force` first: else its rsync pod would hold `<claim>-move`. The undo deletes the new volume too: it sets the reclaim policy of the volume of `<claim>-move` to `Delete` before it deletes that claim, because a class with the policy `Retain`, such as `longhorn`, keeps the volume of a deleted claim. From the point of no return on, a failure leaves Argo CD paused, because a self-heal would make an empty claim. The command then prints the saved claim and the steps that did not run.

pv-migrate runs its pods as root, so that rsync keeps the owner and the group of each file. A namespace with the label `pod-security.kubernetes.io/enforce: restricted` refuses such a pod. There, the move adds `--non-root`: pv-migrate gives its pods the security context that `restricted` asks for, runs them as user 10000, and keeps no owner and no group of a file. User 10000 cannot set the mode of the root folder of the new volume, which root owns, so `rsync -a` would end with exit 23 (`failed to set permissions on "/dest/."`). So the move also gives rsync `--no-perms` (`--rsync-extra-args=--no-perms`): the root folder keeps its mode, and each new file and folder gets the mode of its source under the umask 022 of the rsync pod: no write bit for the group and the others, and no setuid, setgid or sticky bit of the source. A new folder takes the setgid bit of its parent folder. The workloads then read the files only through their `fsGroup`: on a volume of a CSI driver whose `fsGroupPolicy` is not `None`, the kubelet gives each file and folder that group each time a pod mounts the volume, adds the bits 0660 to each file and the setgid bit and 0770 to each folder. So after such a move, each file is writable by the group whatever its source mode (a file of 0444 becomes 0664), and each folder has 2775. So in such a namespace the plan refuses a workload whose pod template has no `fsGroup`, and a class with no such driver, such as `local-path`. To keep the owners, move the claim while the namespace enforces `baseline`. pv-migrate as user 10000 also cannot read a file that only its owner can read, and then the copy fails and the move undoes its steps.

The old volume stays `Released`, with its data, until a person deletes it. The command prints the command that deletes it: with the reclaim policy `Delete`, local-path deletes the volume and its directory on the node.

```bash
kubectl patch pv <old-pv> -p '{"spec":{"persistentVolumeReclaimPolicy":"Delete"}}'
```

#### Change the class of a volume

`--storage-class <class>` moves the data to a new volume of that class, such as the replicated class `longhorn` (Replicated Volumes), and keeps the name of the claim. The class of a claim cannot change after its create, so a claim of `volumeClaimTemplates` can get another class only through this move. The target node must be able to attach a volume of the class: when a CSIDriver has the name of the provisioner of the class, the CSINode of the node must list that driver. Without `--to-node`, the command picks the node with the most free disk of those nodes, and that can be the node of the old volume.

`--access-mode <mode>` gives `<claim>-move` and the claim made again that access mode, such as `ReadWriteMany` for a claim that pods on more than one node mount. The access modes of a bound claim cannot change either, so this needs the move too. A Longhorn volume with `ReadWriteOnce` attaches to one node only: a claim of several pods on a `local-path` volume, which holds all of them on its node, becomes `ReadWriteMany` on `longhorn`, which Longhorn serves over NFS from a share manager pod. Without the option, both claims keep the access modes of the old claim, and `--plan` prints the modes before and after the move.

1. Compare the data with the size of the claim. local-path does not limit a volume to its size, but `longhorn` does. When the data does not fit, the copy fails and the move undoes its steps. Give the new claim a larger size with `--size <quantity>`, such as `--size 10Gi`, and set the same size in git: the move takes the size of the live claim, and a bound local-path claim cannot grow. `--plan` prints the size before and after the move, and the plan refuses a size under the size of the claim.
2. Merge the class change in git, then run the move soon after. Until the move, Argo CD cannot apply the class to the live claim (`spec is immutable after creation`), so the sync of the Application fails, and the workload keeps its data. A merge after the move fails the sync in the same way, until the merge.
3. For a StatefulSet, the API server refuses a change of the class in `volumeClaimTemplates` too. Delete the StatefulSet and keep its pods: `kubectl delete statefulset <name> -n <namespace> --cascade=orphan`. Argo CD makes it again from git, and the new StatefulSet adopts the pods. Do this before or after the move: the claim keeps its name, so the StatefulSet uses it.

#### Finish a stopped move

When a move stops after the point of no return, the old claim is gone, the new volume has the copy, and Argo CD stays paused. Do the steps that the command prints:

1. Make the claim again from the saved file with `spec.volumeName: <new-pv>`, and, after a class change, `spec.storageClassName: <class>`. Leave out `kubectl.kubernetes.io/last-applied-configuration` and the annotations of the volume controllers (`pv.kubernetes.io/*`, `volume.kubernetes.io/*`, `volume.beta.kubernetes.io/*`). Then put the saved last-applied value back with `kubectl annotate pvc <claim> -n <namespace> --overwrite kubectl.kubernetes.io/last-applied-configuration=<value>`.
2. Scale the workloads back to their replicas, and make sure that their pods run on the target node (after a class change, that they run).
3. Turn on automated sync again: the Application, then `bootstrap`, which restores `cluster`, which restores the others from git.

## Service levels

The [SRE guideline](../docs/guidelines/sre.md) sets how a project runs its services, and the [production readiness guideline](../docs/guidelines/production-readiness.md) sets the rows that each service meets. [The guideline index](../docs/guidelines/index.md) lists each guideline. This section holds the SLOs of the product and the decisions of the owner about them. The decisions about one cluster are in `k8s/README.md` of dan-petty/homelab. [Tracker #5541](https://github.com/dan-petty/devops-cli/issues/5541) holds the open SRE and production readiness gaps, so this section holds no gap row. The service dashboards, `devops prometheus rules` and `devops roadmap review run` give the measured values.

`catalog.toml` of the environment tree is the catalog data: the Applications, the tier, the data class and the dependencies of each service. `devops k8s catalog` reads it. A new service adds its entry in the pull request that adds the service (rule SRE1).

**SLOs.** The window of each SLO is 28 days. SLO 5 is the default of the service dashboards (`monitoring/dashboards/services.toml` of the environment tree) until the owner sets another target. Each other SLO is a Sloth spec under `devops/monitoring/slos/`, and the spec holds its objective, its error budget and the window: `src/devops_cli/prometheus/slo_rules.py` renders the rule groups of `devops/monitoring/prometheus-rules-values.yaml` from the specs, and the `k8s` row of `devops ci` refuses a spec that nobody rendered. SLO 5 has no spec yet, so its objective stays in this table.

| SLO | Service | SLI: good events / valid events | Spec | Objective | Error budget |
| :--- | :--- | :--- | :--- | ---: | ---: |
| 1 | Roadmap Service | Row runs with `result="success"` / row runs with `result` `success` or `error`, for each row and repository (`devops_cli_service_jobs_total`) | [`slos/roadmap-service-rounds.yaml`](devops/monitoring/slos/roadmap-service-rounds.yaml) | — | — |
| 2 | Runner Jobs | Runner Jobs (`devops-cli-implement-*`, `devops-cli-runner-*`) that end in under 3,600 s / runner Jobs that end | [`slos/runner-jobs-duration.yaml`](devops/monitoring/slos/runner-jobs-duration.yaml) | — | — |
| 3 | LLM gateway | Gateway requests with no failure / gateway requests (`litellm_proxy_*_requests_metric_total`) | [`slos/llm-gateway-requests.yaml`](devops/monitoring/slos/llm-gateway-requests.yaml) | — | — |
| 4 | LLM gateway | Gateway requests that end in under 60 s / gateway requests (`litellm_request_total_latency_metric_bucket`) | [`slos/llm-gateway-latency.yaml`](devops/monitoring/slos/llm-gateway-latency.yaml) | — | — |
| 5 | Roadmap Service | Ingress requests with no 5xx answer / ingress requests (`traefik_service_requests_total`) | — | 99.9 % | 0.1 % of the requests |

SLO 2 counts only the runner Jobs that end. kube-state-metrics shows a Job only while the Job object exists, and a failed Job has no completion time.

**Owner values.**

- **Incident trigger 1.** A burn rate of 14.4x or more for 1 hour or more, with at least 20 events. 14.4x is the 1-hour page rate of a 30-day window. The default of the guideline for 28 days is 13.44x. The value stays here until the settings of the incident job (#5477) hold it.
- **Pages.** One owner holds one 12-hour shift each day, so the page budget is 2 pages a day.

**Accepted exceptions.**

- Git does not hold the Secrets ([Cluster Secrets](#cluster-secrets)) or ConfigMap `devops-cli-config` ([Homelab Values at Deploy Time](#homelab-values-at-deploy-time)).
- The sweep and its Valkey keep state on `local-path` volumes, which stop with their node ([ADR 0021](../docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md)). The off-node backup of owned state limits the loss.
- The roadmap Service runs one replica with no PodDisruptionBudget. A release rolls with a surge (`maxSurge: 1`, `maxUnavailable: 0`) and has no gap, but a drain of its node still stops the webhooks for a time ([Roadmap service](../docs/CLUSTER.md#roadmap-service), #4575).

**Runbooks for the whole system:** the [stop switch](../docs/CLUSTER.md#stop-switch), the planned maintenance (`k8s/README.md` of dan-petty/homelab), the [recovery of Argo CD](#recovery) and the [failure recovery matrix](../docs/ROUTINE_TASKS.md#4-failure-recovery--troubleshooting-matrix).

## Alerting

The [SRE guideline](../docs/guidelines/sre.md) sets the method of the SLOs, the burn-rate alerts, the page and ticket targets and the incident steps. [Service levels](#service-levels) holds the SLOs. This section holds the rules of the product. The rules of the cluster, Alertmanager, its receiver and the planned maintenance are in `k8s/README.md` of dan-petty/homelab (Alerting).

The product rules, the groups that select a `devops_cli_*` series, are in `devops/monitoring/prometheus-rules-values.yaml`, under `serverFiles.devops_cli_alerting_rules.yml` (#5292). The `prometheus` Application of the environment gives the chart this file after the values of the environment, and `devops k8s deploy-stack` gives `helm upgrade` the files in the same order. The row work series that more than one consumer reads have a group of recording rules (#4562): the group `roadmap-service-recording` records `repo_lane_row:devops_cli_service_jobs_total:increase1h`, the failed jobs of the last hour by repository, lane, row and result, `service:devops_cli_service_budget_requests_per_limit:ratio`, the spent requests of the last hour over the hourly budget, and `repo_row_class:devops_cli_service_job_suspended:max`, the rows that wait after a failed round by repository, row and class. Each rule of the group matches `job=~"roadmap-service|roadmap-.+"` and drops the `job` label, so one recorded series holds the series of the Service and of a `roadmap-<row>` pod, and a move of the row work changes one name in the group and no consumer. The row work alerts `RoadmapServiceJobsFailing`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceRowSuspended` read the recorded series, and the router health selectors keep `job="roadmap-service"`, because the router keeps its own job. The cases of the group are in `tests/fixtures/prometheus_rules/roadmap_service_recording_tests.yaml`.

| Alert | Fires when | For | Severity |
| :--- | :--- | :--- | :--- |
| `RagIngestBehind` | No RAG ingestion run succeeded for repository `{{ $labels.repo }}` in the last two schedule periods (360s) | — | warning |
| `ResearchCriticalFindings` | The last `devops research sweep` of the last 7 days found a critical advisory that affects a pin of the project (#3899). The sweep sets zero for a severity with no finding, so a clean sweep ends the alert. A sweep with a lookup that got no answer sets no value. Read the candidates that the sweep filed, or run `devops research advisories`, and update the pin. Run the sweep again | — | critical |
| `RepositorySettingsDrift` | The last nightly drift check of the last 2 days (CronJob `repos-drift`, #6783) found rows of a repository of `service.repos` off the baseline of the template repository: `pending`, `failed` or `waiting`. Read the rows in the log of the last Job of `repos-drift`, or run `devops repos onboard <owner>/<name> --plan` with your own login. Then apply the baseline with `--confirm`, or change the baseline in the template repository ([onboard](../docs/repos/onboard.md#the-nightly-job)) | — | warning |
| `RepositorySettingsUnreadable` | The last nightly drift check of the last 2 days could not read rows of a repository, so it cannot say that the repository matches its baseline. A not readable row never fires `RepositorySettingsDrift`. The log of the last Job of `repos-drift` gives the reason of each row: a runner image with no `copier` program (dan-petty/devtools pull request 43), or a permission that the token of the drift check does not have. Fix the image or the permission set `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS`. GitHub gives the merge settings of row 2 only with Contents write and `bypass_actors` of row 10 only with Administration write, so the installation must grant both (#6888) | — | warning |
| `RepositoryDriftCheckStopped` | CronJob `repos-drift` sent a result in the last 7 days but none in the last 2 days. An error before the reports, such as a refused App token, sends no result. Read the status and the log of its last Job with `kubectl -n devops get jobs -l app.kubernetes.io/name=repos-drift` | — | warning |
| `ClaudeSpendDailyHigh` | The calls of `claude-sonnet-5-5` cost more than 15 USD in the last 24 hours (#4222). The rule sums the 24 hour increase of `devops_cli_ai_spend_usd_total` of every job, and keeps the spend of a counter that reset. The highest normal day is 5.59 USD, and a failed stage burst costs about 21 USD per hour. Read the cost page of the AI spend dashboard, find the caller by the `end_user` label, and stop the job. Set the threshold again with the data of a month | — | warning |
| `HostedSpendDailyHigh` | The calls of all hosted models cost more than 25 USD in the last 24 hours (#4222). A local request adds 0 to `devops_cli_ai_spend_usd_total`, so the sum is the hosted spend. Read the cost page of the AI spend dashboard, find the caller by the `end_user` label, and stop the job | — | warning |
| `RoadmapServiceIdentityRefused`, `RoadmapServiceGitHubThrottled`, `RoadmapProviderKeySpendLimit` | GitHub refused the identity of the roadmap Service, or throttled its requests, or the provider key behind the LLM gateway reached its spend limit; see [docs/CLUSTER.md](../docs/CLUSTER.md#alerts), Roadmap service, Alerts | — | critical |
| `RoadmapServiceJobsFailing` | All jobs of one row of a repository failed in 1 hour, from the recorded series `repo_lane_row:devops_cli_service_jobs_total:increase1h` of the group `roadmap-service-recording` | 30m | warning |
| `RoadmapServiceLaneStalled`, `RoadmapServiceRestarted`, `RoadmapServiceMemoryNearLimit`, `RoadmapServiceUnavailable`, `RoadmapServiceGitHubRequestsHigh`, `RoadmapServiceModelRequestsHigh`, `RoadmapServiceStateUnkept`, `RoadmapServiceRowSuspended` | The roadmap Service stalls, its pod restarts, uses almost all of its memory limit or is unavailable, its GitHub or model requests in an hour are high, it could not write a state record, or a row stays suspended; `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceRowSuspended` read the recorded series `service:devops_cli_service_budget_requests_per_limit:ratio` and `repo_row_class:devops_cli_service_job_suspended:max` of the group `roadmap-service-recording`; see [docs/CLUSTER.md](../docs/CLUSTER.md#alerts), Roadmap service, Alerts | 0–15m | warning |
| `RoadmapServiceWebhooksRejected` | The webhook route of the roadmap Service rejected more than 20 deliveries in 15 minutes; see [docs/CLUSTER.md](../docs/CLUSTER.md#alerts), Roadmap service, Alerts | — | warning |
| `RoadmapServiceRoundsPage1h` | The 1-hour and the 5-minute error ratios of the roadmap Service rounds SLO of one repository and row are above 13.44 times its 1 % error budget, and the 1-hour window holds 20 runs or more. Do this: read the failing row in `devops roadmap inbox`, and the log of the Service pod (`kubectl -n devops logs deployment/roadmap-service`) | — | critical |
| `RoadmapServiceRoundsPage6h` | The 6-hour and the 30-minute error ratios of the roadmap Service rounds SLO of one repository and row are above 5.6 times its error budget, and the 6-hour window holds 20 runs or more. Do this: as for `RoadmapServiceRoundsPage1h`, then comment the cause on the open issue of the row | — | critical |
| `RoadmapServiceRoundsTicket1d` | The 1-day and the 2-hour error ratios of the roadmap Service rounds SLO of one repository and row are above 2.8 times its error budget, and the 1-day window holds 20 runs or more. Do this: open an issue for the failing row with `devops roadmap intake`, and read the trend on the Service dashboard | — | warning |
| `RoadmapServiceRoundsTicket3d` | The 3-day and the 6-hour error ratios of the roadmap Service rounds SLO of one repository and row are above 0.93 times its error budget, and the 3-day window holds 20 runs or more. Do this: open an issue for the failing row, or change the objective of the SLO in its Sloth spec | — | warning |
| `RunnerJobsDurationPage1h` | The 1-hour and the 5-minute error ratios of the runner Jobs duration SLO are above 13.44 times its 10 % error budget, which is an error ratio of 1.344. The ratio of this SLI is at most 1, so this page never fires, and it stays for the shape of Table 2 of the SRE guideline. Do this: read `RunnerJobsDurationPage6h` and the runner Jobs of `kubectl -n devops get jobs -l app.kubernetes.io/component=roadmap-implement` | — | critical |
| `RunnerJobsDurationPage6h` | The 6-hour and the 30-minute error ratios of the runner Jobs duration SLO are above 5.6 times its error budget, and the 6-hour window holds 20 Jobs or more. Do this: read the runner Jobs with `kubectl -n devops get jobs -l app.kubernetes.io/component=roadmap-implement`, and the log of the Job that ran over 3,600 s | — | critical |
| `RunnerJobsDurationTicket1d` | The 1-day and the 2-hour error ratios of the runner Jobs duration SLO are above 2.8 times its error budget, and the 1-day window holds 20 Jobs or more. Do this: open an issue for the Jobs that ran over 3,600 s with `devops roadmap intake` | — | warning |
| `RunnerJobsDurationTicket3d` | The 3-day and the 6-hour error ratios of the runner Jobs duration SLO are above 0.93 times its error budget, and the 3-day window holds 20 Jobs or more. Do this: open an issue for the slow Jobs, or change the 3,600 s limit or the objective of the SLO in its Sloth spec | — | warning |
| `LlmGatewayRequestsPage1h` | The 1-hour and the 5-minute error ratios of the LLM gateway requests SLO are above 13.44 times its 0.5 % error budget, and the 1-hour window holds 20 requests or more. Do this: read the request panels of the LLM stack dashboard and the log of the gateway pod (`kubectl -n llm logs deployment/llm-gateway`); a refused provider key or a cooled backend is the cause | — | critical |
| `LlmGatewayRequestsPage6h` | The 6-hour and the 30-minute error ratios of the LLM gateway requests SLO are above 5.6 times its error budget, and the 6-hour window holds 20 requests or more. Do this: as for `LlmGatewayRequestsPage1h`, then comment the cause on the open issue of the gateway | — | critical |
| `LlmGatewayRequestsTicket1d` | The 1-day and the 2-hour error ratios of the LLM gateway requests SLO are above 2.8 times its error budget, and the 1-day window holds 20 requests or more. Do this: open an issue for the failing requests with `devops roadmap intake` | — | warning |
| `LlmGatewayRequestsTicket3d` | The 3-day and the 6-hour error ratios of the LLM gateway requests SLO are above 0.93 times its error budget, and the 3-day window holds 20 requests or more. Do this: open an issue for the failing requests, or change the objective or the backend of the SLO in its Sloth spec | — | warning |
| `LlmGatewayLatencyPage1h` | The 1-hour and the 5-minute error ratios of the LLM gateway latency SLO are above 13.44 times its 5 % error budget, and the 1-hour window holds 20 requests or more. Do this: read the latency panels of the LLM stack dashboard and the log of the gateway pod (`kubectl -n llm logs deployment/llm-gateway`); a backend that holds a call past 60 s is the cause | — | critical |
| `LlmGatewayLatencyPage6h` | The 6-hour and the 30-minute error ratios of the LLM gateway latency SLO are above 5.6 times its error budget, and the 6-hour window holds 20 requests or more. Do this: as for `LlmGatewayLatencyPage1h`, then name the slow backend in a comment on the open issue of its cause | — | critical |
| `LlmGatewayLatencyTicket1d` | The 1-day and the 2-hour error ratios of the LLM gateway latency SLO are above 2.8 times its error budget, and the 1-day window holds 20 requests or more. Do this: open an issue for the slow backend with `devops roadmap intake`, and read the trend on the LLM stack dashboard | — | warning |
| `LlmGatewayLatencyTicket3d` | The 3-day and the 6-hour error ratios of the LLM gateway latency SLO are above 0.93 times its error budget, and the 3-day window holds 20 requests or more. Do this: open an issue for the slow backend, or change the objective or the backend of the SLO in its Sloth spec | — | warning |

## Cluster Secrets

Every Secret the stacks read comes from the workstation's OS keyring. `devops k8s push-secrets` writes them (workstation keyring → cluster, the reverse of `devops k8s sync-secrets`), and `devops k8s deploy-stack` runs the same push right after the namespaces, before any manifest or Helm release. The table of a cluster is the rows of `cluster-secrets.toml` of the environment tree, then the product rows of `src/devops_cli/k8s/cluster_secrets.py`. A command fails when the environment tree has no `cluster-secrets.toml`. A pod that references a Secret with no row does not start: `kubectl -n <namespace> get pods` shows `CreateContainerConfigError`, and Argo CD shows the Application as degraded. Add a new secret as a row with a generator, in the file of the repository that holds its consumer, so that `push-secrets` makes its value: an agent writes no secret value. Argo CD applies a manifest when it merges, and a pod that reads a missing Secret does not start. So a person runs `uv run devops k8s push-secrets --only <namespace>/<name>` from the branch of the pull request before the merge of the manifest that reads the new Secret. Run `devops k8s push-secrets --only <namespace>/<name> --plan` and merge only when the plan shows `unchanged` (#6064). Make the reference `optional: true` when the pod can start without it. A pull request that adds a Secret reference names the push command as its first line, so the person pushes the Secret before the merge (#5200). Check the pods after the merge. The product rows:

| Secret | Key | Source | Required | When the keyring has no value | Stack | Restarted when it changes |
|---|---|---|---|---|---|---|
| `llm/valkey-runs-auth` | `password` | keyring `runs_index_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-runs` |
| `llm/valkey-devops-auth` | `password` | keyring `valkey_devops_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-devops` |
| `llm/valkey-devops-auth` | `sweep` | keyring `valkey_devops_sweep` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-devops` |
| `llm/valkey-devops-auth` | `brain` | keyring `valkey_devops_brain` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-devops` |
| `llm/valkey-devops-auth` | `agent` | keyring `valkey_devops_agent` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-devops` |
| `llm/valkey-devops-auth` | `metrics` | keyring `valkey_devops_metrics` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-devops` |
| `llm/valkey-devops-auth` | `users.acl` | derived from keyring valkey_devops_password, keyring valkey_devops_sweep, keyring valkey_devops_brain, keyring valkey_devops_agent, keyring valkey_devops_metrics | yes | fail | llm | `deployment/valkey-devops` |
| `devops/valkey-roadmap-auth` | `brain` | keyring `valkey_roadmap_brain` | yes | adopt the live value; else generate 64 hex | devops | `deployment/valkey-roadmap`, `deployment/roadmap-service` |
| `devops/valkey-roadmap-auth` | `agent` | keyring `valkey_roadmap_agent` | yes | adopt the live value; else generate 64 hex | devops | `deployment/valkey-roadmap`, `deployment/roadmap-service` |
| `devops/valkey-roadmap-auth` | `metrics` | keyring `valkey_roadmap_metrics` | yes | adopt the live value; else generate 64 hex | devops | `deployment/valkey-roadmap`, `deployment/roadmap-service` |
| `devops/valkey-roadmap-auth` | `users.acl` | derived from keyring valkey_roadmap_brain, keyring valkey_roadmap_agent, keyring valkey_roadmap_metrics | yes | fail | devops | `deployment/valkey-roadmap`, `deployment/roadmap-service` |
| `devops/crawl4ai` | `CRAWL4AI_API_TOKEN` | keyring `crawl4ai_api_token` | yes | adopt the live value; else generate `token_urlsafe(32)` | devops | `deployment/crawl4ai` |
| `devops/searxng` | `SEARXNG_SECRET` | keyring `searxng_secret_key` | yes | adopt the live value; else generate 64 hex | devops | `deployment/searxng` |
| `devops/searxng-metrics-auth` | `username` | literal | yes | fail | devops | `deployment/searxng` |
| `devops/searxng-metrics-auth` | `password` | keyring `searxng_metrics_password` | no | adopt the live value; else skip with a warning | devops | `deployment/searxng` |
| `devops/mcp-server` | `DEVOPS_CLI_MCP_TOKEN` | keyring `mcp_token` | yes | adopt the live value; else generate `token_urlsafe(32)` | devops | `deployment/mcp-server` |
| `devops/infra-ssh-key` | `id_ed25519` | keyring `infra_ssh_private_key` | no | adopt the live value; else skip with a warning | devops | none |
| `devops/renovate` | `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID` | setting renovate.github_app_id | no | skip with a warning | devops | none |
| `devops/renovate` | `DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID` | setting renovate.github_app_installation_id | no | skip with a warning | devops | none |
| `devops/renovate` | `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY` | keyring `renovate_github_app_private_key` | no | adopt the live value; else skip with a warning | devops | none |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` | keyring `service_github_app_private_key` | yes | adopt the live value; else fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_AI_API_KEY` | keyring `llm_gateway_master_key` | yes | adopt from `llm/llm-gateway-secrets master-key`; else fail | devops | `deployment/roadmap-service` |
| `devops/roadmap-service-llm-key` | `api-key` | keyring `roadmap_service_llm_key` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` | keyring `service_webhook_secrets` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_FIRECRAWL_API_KEY` | keyring `firecrawl_api_key` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_VALKEY_PASSWORD` | keyring `valkey_devops_password` | yes | adopt from `llm/valkey-devops-auth password`; else generate 64 hex | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN` | keyring `mattermost_command_token` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_CRAWL4AI_API_TOKEN` | keyring `crawl4ai_api_token` | no | adopt from `devops/crawl4ai CRAWL4AI_API_TOKEN`; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_MCP_STAGE_TOKEN` | keyring `mcp_token` | no | adopt from `devops/mcp-server DEVOPS_CLI_MCP_TOKEN`; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` | keyring `mcp_token` | no | adopt from `devops/mcp-server DEVOPS_CLI_MCP_TOKEN`; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_QDRANT_API_KEY` | keyring `qdrant_read_only_api_key` | yes | adopt from `llm/qdrant-api-key read-only-api-key`; else generate `token_urlsafe(32)` | devops | `deployment/roadmap-service` |
| `devops/qdrant-api-key` | `api-key` | keyring `qdrant_api_key` | yes | adopt from `llm/qdrant-api-key api-key`; else generate `token_urlsafe(32)` | devops | none |

- The keyring must be unlocked (`devops devcontainer unlock-keyring`); a locked or missing keyring stops the push before anything is read or written, and stops deploy-stack before it applies anything.
- A value the keyring lacks but the cluster holds is adopted into the keyring, so a first push changes nothing live. Only values nobody types are generated, and each is stored in the keyring before it is pushed.
- Typed values are stored at a hidden prompt: `devops config set service.github_app.private_key --from-file <key.pem>` or `devops config set gitea.admin_password`.
- A derived entry is built from other values of the same push, such as a connection string from a user and a password. The push resolves every other entry first, then fills each field of the entry's template with the value of its input, quoted with `urllib.parse.quote(..., safe="")`. It never adopts, generates or stores a derived value, and a live value that differs needs `--rotate`. `--plan` names the source as `derived from` and its inputs, and `--dry-run` shows a placeholder.
- A row may name its Secret type, such as `kubernetes.io/basic-auth`. The default is `Opaque`. Kubernetes cannot change the type of an existing Secret, so a row names its type before its first push.
- `CRAWL4AI_API_TOKEN` is the bearer token of Crawl4AI, which refuses to listen beyond loopback without it. One keyring value, `crawl4ai_api_token`, feeds Secret `devops/crawl4ai` and the key `DEVOPS_CLI_CRAWL4AI_API_TOKEN` of Secret `devops/devops-cli`, so the client and the service always hold the same token. `devops config set crawl4ai.api_token --generate` makes the token with the generator that the cluster Secret table declares and stores it in the OS keyring; `--rotate` replaces a stored token. A person runs `devops k8s push-secrets --only devops/crawl4ai --only devops/devops-cli` to create or change the two Secrets; no other command writes them.
- `DEVOPS_CLI_MCP_TOKEN` is the bearer token of the MCP server, which refuses to start without it (`mcp.token`, SECURITY.md, MCP Server on the Network). The server accepts one token, so one keyring value, `mcp_token`, feeds Secret `devops/mcp-server` (read by Deployment `mcp-server` with `secretKeyRef`) and the keys `DEVOPS_CLI_MCP_STAGE_TOKEN` and `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` of Secret `devops/devops-cli` (the tokens of the stage and implement clients, `mcp.stage_token` and `mcp.implement_token`). A person runs `devops k8s push-secrets --only devops/mcp-server --only devops/devops-cli` to create or change them; a change restarts `deployment/mcp-server` and `deployment/roadmap-service`. The clients stay off until a person sets `roadmap.stage.mcp` or `roadmap.implement.mcp` in the ConfigMap, and the `roadmap.mcp.url` setting names the server. The setting alone is not sufficient: a stage Job and a runner Job take only the keys of `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS` (#6518), so the client sends no token and the server answers 401. The change that turns a client on also adds its key (`DEVOPS_CLI_MCP_STAGE_TOKEN` or `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN`) to the template of the Job (`k8s/devops/cronjob-stage.yaml` or `k8s/devops/cronjob-runner.yaml`) and to the key list of the admission policy `roadmap-service-jobs`. Two NetworkPolicies let the clients reach the server (`mcp-server-ingress` and `mcp-server-clients`, TCP 8001 only, to the pods of the server only). Both select the clients by the label `app.kubernetes.io/name`: `roadmap-service`, and `devops-cli-job`, the label that `build_job` sets on every Job pod. A pod with the label of the CronJob template, `devops-cli-runner`, never runs, so no policy names it (#4355).
- `devops/valkey-roadmap-auth` holds the ACL users of `valkey-roadmap` ([valkey-roadmap](../docs/CLUSTER.md#valkey-roadmap)). The push generates the passwords of `brain`, `agent` and `metrics`, and builds the aclfile `users.acl` from them in the same push. Their keyring values, `valkey_roadmap_brain`, `valkey_roadmap_agent` and `valkey_roadmap_metrics`, are no managed credentials: no setting reads them. The pod of `valkey-roadmap` mounts `users.acl` and does not start without it, so a person runs `devops k8s push-secrets --only devops/valkey-roadmap-auth` before the merge of a manifest that reads a new key. A client pod reads the key of its user with `secretKeyRef`, as `DEVOPS_CLI_ROADMAP_STATE_PASSWORD`: Deployment `roadmap-service` reads key `brain` (#4676). A changed password restarts `deployment/valkey-roadmap`, which reads the aclfile only at its start, and then `deployment/roadmap-service`, which reads the password of `brain` only at its start.
- `SEARXNG_SECRET` is the server secret of SearXNG, which refuses to start with its default key. Its keyring value, `searxng_secret_key`, is no managed credential: no setting reads it, and only the pod does. A person runs `devops k8s push-secrets --only devops/searxng` to create or change it, and a change restarts `deployment/searxng`.
- `devops/searxng-metrics-auth` is the basic-auth Secret of the OpenMetrics endpoint of SearXNG ([SearXNG](../docs/CLUSTER.md#searxng)). The Secret is optional: SearXNG starts and searches without it, and only the endpoint is off. The user is the literal `searxng`, and its keyring value, `searxng_metrics_password`, is no managed credential: no setting reads it. The init container `render-settings` reads the password through an optional reference and writes it into the rendered settings file, and the ServiceMonitor sends both keys to the scrape. When the Secret has no password, `render-settings` logs one line that names the Secret and turns the endpoint off. A push with no keyring value and no live value skips the password with a warning. To turn the endpoint on, a person stores the password at a hidden prompt with `uv run keyring set devops-cli searxng_metrics_password`, then runs `devops k8s push-secrets --only devops/searxng-metrics-auth`. A push that adds the password to an existing Secret restarts `deployment/searxng`. A push that creates the Secret restarts nothing, so the person then runs `kubectl -n devops rollout restart deployment/searxng`.
- `devops/renovate` holds the GitHub App `dan-petty-renovate` that self-hosted Renovate acts as ([Renovate](../docs/CLUSTER.md#renovate)). Its keys are the variables of `renovate.github_app_id`, `renovate.github_app_installation_id` and `renovate.github_app_private_key`, so the init container `token` of CronJob `renovate` reads them with `envFrom`, and no other container reads the Secret. Store the values with `devops config set renovate.github_app_id <app-id>`, `devops config set renovate.github_app_installation_id <installation-id>` and `devops config set renovate.github_app_private_key --from-file <key.pem>`, then run `devops k8s push-secrets --only devops/renovate --plan` and `devops k8s push-secrets --only devops/renovate`. Each run reads the Secret at its start, so no workload restarts, and the `homelab` project of Argo CD ignores the pushed Secret as an orphan. Renovate is an optional feature: a push with no Renovate settings skips the three keys and writes no Secret, and the `token` container then names the settings that are not set and stops the run. Push it to one cluster only: two clusters that run Renovate as the same App push to the same branches.
- `devops/infra-ssh-key` holds the private key of the infra SSH key in its key `id_ed25519` ([Infra drift](../docs/CLUSTER.md#infra-drift)). WorkflowTemplate `infra-drift` mounts the Secret read-only at `/secrets/ssh`, and Ansible reads the key as `ANSIBLE_SSH_PRIVATE_KEY_FILE`. The pod does not start without the Secret. The keyring value, `infra_ssh_private_key`, is the managed credential `infra.ssh_private_key`. Store it with `devops config set infra.ssh_private_key --from-file <key-file>`. The file is the newest `<prefix>-id_ed25519-<YYYYMMDD>` file of `ssh.key_dir`, where `<prefix>` is the `ssh_key_prefix` of the entries of `infra.repos`. Do not use `keyring set`: it removes the last newline of the input from a pipe, and OpenSSH refuses a private key without that newline. Then run `devops k8s push-secrets --only devops/infra-ssh-key --plan` and `devops k8s push-secrets --only devops/infra-ssh-key`. Each Workflow pod mounts the Secret at its start, so no workload restarts. A push with no keyring value and no live value skips the Secret with a warning, and it writes the other Secrets of the stack. When the infra SSH key changes, store the new key and push with `--rotate`.
- `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` is the private key of GitHub App `devops-cli-service`, which the roadmap Service and the cluster Jobs act as ([ADR 0015](../docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md)). Store it with `devops config set service.github_app.private_key --from-file <key.pem>`. A pod whose environment holds the key acts as the App: it mints an installation token, mints a new one before the token expires, and gives the current token to each gh and git child as GH_TOKEN. A workstation keeps the key only in the keyring, so a workstation run keeps the gh login of its person.
- `DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN` holds the authentication token that verifies `/roadmap` slash command requests from Mattermost to the Service's webhook router. Store the token with `devops config set mattermost.command_token`, then push with `devops k8s push-secrets --only devops/devops-cli`.
- `devops` rows are pushed wherever namespace `devops` exists, also by every deploy-stack run. `devops k8s deploy-stack --no-push-secrets` skips the push on a cluster without a keyring.
- `gitea` rows are pushed by `push-secrets` with no `--stack` or with `--stack gitea`, and by `deploy-stack --stack gitea` or `all`. Where namespace `gitea` exists, these pushes need the Gitea admin password in the keyring. A deploy of another stack never reads it.
- `chat` rows are pushed by `push-secrets` with no `--stack` or with `--stack chat`, and by `deploy-stack --stack chat` or `all`. The database password is generated or adopted, and `DB_CONNECTION_STRING` is derived from it.
- Secrets are server-side applied from stdin under field manager `devops-cli`, labelled `app.kubernetes.io/managed-by: devops-cli`, with values in `data`: never in argv, a file, an annotation or the output. A Secret still carrying a client-side apply's `kubectl.kubernetes.io/last-applied-configuration` loses it.
- `--plan` reads the keyring and the live Secrets, says so, and prints each key's state (`would adopt`, `unchanged`, `differs`, ...) and the workloads a change would restart, writing nothing. `--dry-run` makes no request at all, not even those reads: it prints the requests a push would make, in order, with `<placeholders>` for every value and the condition under which each later request runs.
- A Secret whose data changed has its workloads restarted (`kubectl rollout restart`); `--no-restart` prints the commands instead.
- `devops/roadmap-service-llm-key` is the virtual key of the roadmap Service on the LLM gateway. `devops k8s bootstrap-roadmap-key` mints it on the gateway with a budget, a requests-per-minute limit and the `devops-*` models, stores it in the keyring as `roadmap_service.llm_key`, and writes Secret `roadmap-service-llm-key` with key `api-key`. The Deployment `devops/roadmap-service` reads `DEVOPS_CLI_AI_API_KEY` from this Secret. The stage Job and the runner Jobs read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli` (owner decision of 2026-11-20, #2695, comment 7045868447, keeps the runner Jobs on the current model key for now). To rotate the key, run `devops k8s bootstrap-roadmap-key --force` and delete the old key on the gateway.

Rotation: a live value that differs from the keyring stops the push. Either replace the live value with the keyring's, or adopt the live value by removing the keyring entry:
```bash
devops k8s push-secrets --only devops/crawl4ai --plan      # reads the cluster; shows "differs"
devops k8s push-secrets --only devops/crawl4ai --rotate     # the keyring's value wins
uv run keyring del devops-cli crawl4ai_api_token                  # or: drop it, and the next push adopts the live value
```
To rotate a generated value, store a new one at a hidden prompt with `uv run keyring set devops-cli <keyring key>`, then push with `--rotate`.

## Agent sessions

Agents may apply manifests, restart workloads, and exercise workloads in the lab cluster (secrets and hardware stay with the owner; see [ADR 0038](../docs/adr/0038-owner-decisions-on-what-agents-may-do.md#decision-1)). `agents/` of the environment tree defines one read-only identity for agent sessions that need read-only access: namespace `agents`, ServiceAccount `devops-agent` with no mounted token, and its binding to ClusterRole `view`. It is not the limit of agent access. `k8s/README.md` of dan-petty/homelab (Agent sessions) gives the details.

## Gitea

Gitea is the internal forge and container registry of the cluster (#1081). Its values and manifests are in `gitea/` of the environment tree. `k8s/README.md` of dan-petty/homelab (Gitea) tells what runs, who reaches it and where its data is.

### Cloudflare

Nothing new is configured in Cloudflare when the wildcard route and the wildcard Access application are in place:

- The tunnel's wildcard public hostname goes to Traefik, and the wildcard DNS record exists. `devops cloudflare tunnel routes` and `devops cloudflare dns list` show them, and `devops cloudflare tunnel sync` and `devops cloudflare dns sync` make them.
- The Access application of the wildcard has the policy `homelab-public-ip-bypass` (the setting `cloudflare.access.bypass_policy_name`) with the current public address of the workstation. `devops cloudflare access status --json` gives the ID of the application, and `devops cloudflare access policies <app-id>` lists its policies.

Git over HTTPS cannot follow the Access login redirect, and a git credential helper gives only a user name and a password, not headers. Thus git gets through Access by the bypass policy, and then Gitea's own token authenticates the request. No Access service token goes into git config. A browser on another network signs in through Access first, and then through Gitea.

When the public address changes, git and the API get a redirect to the Access login. Set `cloudflare.access.allowed_emails` and `cloudflare.access.bypass_ips` (the new address), then run:

```bash
devops cloudflare access sync --domain '*.<domain>' --dry-run   # it must name the wildcard application and both lists
devops cloudflare access sync --domain '*.<domain>'
```

Without `--domain`, the command updates the apex application. Without the emails, it empties the allow policy. If git gets a Cloudflare challenge page instead of the reply of Gitea, the bot or WAF settings of the zone challenge the git client: exempt host `git.<domain>` from that challenge.

### Rollout

1. Store the admin password at a hidden prompt: `uv run devops config set gitea.admin_password`. The admin user is `gitea_admin`.
2. Merge the environment change. The Applications of Gitea sync. The Gitea pod waits in `CreateContainerConfigError` until Secret `gitea-admin` exists.
3. Run `uv run devops k8s deploy-stack --stack gitea --context <context>`. It pushes Secret `gitea/gitea-admin` and sets the git host on Application `ingress`. Then the pod starts with no other step.
4. Set the reclaim policy of the bound volume to `Retain`, because `local-path` deletes the data with a deleted claim:
   ```bash
   kubectl patch pv "$(kubectl -n gitea get pvc gitea-shared-storage -o jsonpath='{.spec.volumeName}')" \
     -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
   ```
5. Run `uv run devops k8s doctor --stack gitea --context <context>`. Every check must pass ([Stack checks](#stack-checks)).

To change the admin password, store the new one with `uv run devops config set gitea.admin_password`, then run `uv run devops k8s push-secrets --only gitea/gitea-admin --rotate`. The push restarts Gitea, and Gitea sets the admin's password to the Secret's when it starts (`passwordMode: keepUpdated`). Then `uv run devops k8s doctor --stack gitea` signs in with the new password in its `clone-url` check.

### Stack checks

`devops k8s doctor --stack gitea` checks the live stack, and shows the result and the reason of each check. It exits 2 when a check fails. A failed check does not stop the next one. `--dry-run` lists the kubectl commands and the HTTP requests, and makes none of them. `--format json` or `yaml` gives the checks as data.

| Check | It passes when |
| :--- | :--- |
| `application-gitea`, `application-gitea-manifests` | the Application is `Synced` and `Healthy`. |
| `volume-retained` | the volume of claim `gitea-shared-storage` has the reclaim policy `Retain` ([Rollout](#rollout), step 4). |
| `pod-security-restricted` | namespace `gitea` has the Pod Security enforce level `restricted`. |
| `ingress-host` | Ingress `gitea/gitea-ingress` has a host, and the host is not `git.example.com`, the placeholder in git. The next checks send their requests to that host of the live Ingress, through the tunnel. Without it, they fail and send nothing. |
| `tunnel-host` | `GET /user/login` answers 200. A redirect to the Access login tells you that the public address changed ([Cloudflare](#cloudflare)). |
| `anonymous-read-refused` | `GET /api/v1/repos/search` with no sign-in answers 401 or 403. |
| `registry-token` | `GET /v2/` answers 401 with a Bearer challenge whose realm starts with `https://git.<domain>/`. |
| `clone-url` | a temporary private repository `devops-doctor-<random>`, which the check makes as `gitea_admin` with the password from the keyring (`gitea.admin_password`), has a `clone_url` that starts with `https://git.<domain>/`, and an `ssh_url` that does not name that host. Gitea 1.27.3 fills `ssh_url` also when SSH is off: it names the in-cluster address, where nothing answers. |
| `temporary-repository-deleted` | Gitea deleted the temporary repository. The check deletes it also when the `clone-url` check fails, and when the create gets no answer. When the delete fails, the reason names the repository to delete by hand. |
| `no-egress` | `curl https://github.com` in the Gitea container cannot connect (curl exits 7 or 28). |

The password goes only into the Authorization header of the create and the delete. It goes into no argument list, log line or output.

### Trials

A trial deploys transient workloads into a fenced cluster namespace from a Gitea branch (#1082).

- **Purpose**: A trial is for new components or test manifests that do not name a managed namespace.
- **Existing stacks**: Changes to an existing stack still go through a pull request to `main` of dan-petty/homelab, or of this repository for the product base. Retargeting a managed Application introduces drift against git and breaks GitOps guarantees.
- **Git URLs**: Argo CD reads repositories from Gitea over in-cluster HTTP (`http://gitea-http.gitea.svc.cluster.local:3000/`). Developers and workstations push to `https://git.<domain>`.
- **Credential setup**: Store a scoped `read:repository` token in the keyring, then push the repository credentials:
  ```bash
  uv run devops config set gitea.argocd_token
  uv run devops k8s push-secrets --only argocd/gitea-repo-creds
  ```
- **Lifecycle**:
  - Start: `uv run devops argo cd trial start --branch <branch> --path <path>` validates the branch and path on Gitea, creates Namespace `trial-<name>`, and applies Application `trial-<name>`.
  - Follow: `uv run devops argo cd apps status trial-<name>` monitors synchronization and health.
  - End: `uv run devops argo cd trial end <name>` deletes Application `trial-<name>`, waits for resources to be removed, and deletes Namespace `trial-<name>`.
- **Network policies**: A trial namespace has no NetworkPolicy by default. A trial must supply its own NetworkPolicy if network isolation is needed.
- **Mainline safety**: Every Application of the environment reads GitHub, not Gitea. If Gitea degrades or fails, production GitOps continues without interruption.

## Mattermost

Mattermost runs under Argo CD from the environment tree, and `k8s/README.md` of dan-petty/homelab (Mattermost) gives its rollout and its operations. After the first sign-up, run `uv run devops k8s bootstrap-mattermost --admin-user <user> --context <context> --k8s-dir <homelab-checkout>/k8s`. It creates the team (`--team`, default the setting `mattermost.team`), the channels `alerts` and `deploys`, an incoming webhook for each channel that is locked to its channel (#1390), and the slash command `/roadmap`. It saves the tokens in the keyring and pushes the Secrets.

## Teardown

These commands read the environment tree, from `--k8s-dir` or `infra.repos`.

```bash
# Teardown infrastructure stack
devops k8s teardown-stack --stack infra

# Teardown LLM stack
devops k8s teardown-stack --stack llm

# Teardown all stacks and namespaces
devops k8s teardown-stack --stack all
```

Teardown leaves the `prometheus-operator-crds` release's CRDs in the cluster. Deleting a CRD deletes every object of its kind, such as every ServiceMonitor, so remove them by hand only when nothing in the cluster uses them. The `argo-workflows` release's Workflow CRDs stay too (`crds.keep`), for the same reason: deleting them deletes every Workflow and WorkflowTemplate. `teardown-stack` reads the environment tree, so give it `--k8s-dir` as `deploy-stack`.

## GitOps

Argo CD maintains the declared state of the homelab cluster from two repositories:

- **dan-petty/homelab** holds the environment, and only it holds the environment. Argo CD reads the Applications, the AppProjects, the values of the charts, the overlays and the dashboards of the cluster from its `main`.
- **This repository** holds the product base. Application `devops` reads `k8s/devops`, and Application `prometheus` reads the rules values file `k8s/devops/monitoring/prometheus-rules-values.yaml`. The environment takes the product dashboards `k8s/devops/dashboards` as a remote base at a release tag.

A change of an environment file is a pull request of dan-petty/homelab. A change of the product base is a pull request here. `k8s/README.md` of dan-petty/homelab (GitOps) gives the topology of the Applications, the drift rule and the prune approval. [Switch Argo CD to the homelab repository](../docs/HOMELAB_REPO_SWITCH.md) records how the environment moved there.

When the root `cluster` Application is present in the cluster, `devops k8s deploy-stack` delegates manifest and Helm reconciliation to Argo CD, and `devops k8s teardown-stack` refuses execution to prevent configuration drift.

### Homelab Values at Deploy Time

This repository is public, so it holds no homelab value. The private infra repo holds the hosts. Ingress hosts sit under the placeholder domain `example.com`, and the devops-cli config holds only its template, `k8s/devops/configmap.example.yaml`. `devops k8s deploy-stack` supplies the real values from `config.yaml` and the keyring:

| Value | Source | Where it lives | Supplied by |
| :--- | :--- | :--- | :--- |
| Secrets | the OS keyring (`devops k8s push-secrets`) | Secrets in the cluster | every stack's deploy, for its Secrets |
| `service.repos`, `service.github_app.app_id`, `service.github_app.installation_id`, `service.github_app.slug`, `service.poll_interval_seconds` | `config.yaml` | ConfigMap `devops-cli-config`, which no Application owns | `--stack devops` or `all` |
| `service.github_requests_per_hour`, only when a source sets it | `config.yaml` or `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` | ConfigMap `devops-cli-config`. With no value set, the ConfigMap holds none, and the Service uses its default of 500 | `--stack devops` or `all` |
| The same settings with every credential-named key removed | `config.yaml`, rendered from the same template | ConfigMap `devops-cli-config-sandbox`, which no Application owns. The planner run Job mounts it at `/config` | `--stack devops` or `all` |
| Hosts under the configured domain | the infra repo | `spec.source.kustomize.patches` of the Application files (`argocd/apps` of the environment tree). Without Argo CD, `deploy-stack` renders the configured domain | Argo CD at each sync, else `deploy-stack` |
| Container environment values under the configured domain: each `env[].value` of a container or init container of a Deployment that holds the placeholder domain, such as `HOMEPAGE_VAR_DOMAIN` | the infra repo | `spec.source.kustomize.patches` of the Application files (`argocd/apps` of the environment tree). Without Argo CD, `deploy-stack` renders the configured domain | Argo CD at each sync, else `deploy-stack` |
| ConfigMap data values under the configured domain: each `data` value of a ConfigMap that holds the placeholder domain, such as `CORS_ALLOW_ORIGIN` of `llm/open-webui-origins` | the infra repo | `spec.source.kustomize.patches` of the Application files (`argocd/apps` of the environment tree). Without Argo CD, `deploy-stack` renders the configured domain | Argo CD at each sync, else `deploy-stack` |

ConfigMap `devops-cli-config-sandbox` is the credential-free copy of that config for the planner run Job ([docs/CLUSTER.md](../docs/CLUSTER.md#roadmap-service)). deploy-stack renders it from the same template and the same active config as `devops-cli-config`, and drops each key of its `devops-cli.yaml` value whose lower-case name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS`, at any depth of maps and lists. A number or a boolean under such a name stays, because a number or a boolean is no credential: each credential of the settings is text. Thus `token_budget`, `step_token_budget` and `item_token_budget` keep their values. The rendered ConfigMap keeps the name and the one data key `devops-cli.yaml` that the run Job mounts, so this repository holds no value of it either. `devops k8s teardown-stack --stack devops` deletes it with `--ignore-not-found`, as it deletes `devops-cli-config`. The dry run names it and prints no value of it.

To change the hourly GitHub request budget of the Service, run `devops config set service.github_requests_per_hour <n>`, then `devops k8s deploy-stack --stack devops`. The Service shows the budget it runs with in `devops_cli_service_budget_limit_requests{job="roadmap-service"}`, and the alert `RoadmapServiceGitHubRequestsHigh` follows that value through the recorded ratio `service:devops_cli_service_budget_requests_per_limit:ratio` of the group `roadmap-service-recording`.

A change of a live value follows these rules:

- A person changes the value with `devops config set` ([AGENTS.md](../AGENTS.md) rule 12). The command keeps a copy of `config.yaml` and a record of the changed keys, with no value.
- Do not change ConfigMap `devops-cli-config` with `kubectl edit` or `kubectl apply`. The next deploy-stack replaces such a change, and no record of it stays.
- deploy-stack also pushes the Secrets of its stack ([Cluster Secrets](#cluster-secrets)). An agent runs it only when `devops k8s push-secrets --stack <stack> --plan` shows each key `unchanged`. If not, a person runs it.
- Write a comment on the issue of the change. Give the key, the reason and the time in UTC, and no secret value.

When `deploy-stack` changes the `data` of `devops-cli-config`, it records the change with no setting values (#5221):

- **Annotations on `devops-cli-config`:** `roadmap.devops-cli/data-sha256`, `roadmap.devops-cli/changed-settings` (comma-joined dotted paths), `roadmap.devops-cli/changed-at` (UTC ISO-8601 ending in `Z`), `roadmap.devops-cli/config-template-commit` (the last git commit touching `k8s/devops/configmap.example.yaml`, omitted outside git), and `roadmap.devops-cli/change-reason` (when `--reason` is passed). When the live `data` digest matches the rendered digest, deploy-stack adds none of these annotations, sends no history patch, and emits no change log.
- **History ConfigMap `devops-cli-config-changes`:** deploy-stack creates ConfigMap `devops-cli-config-changes` in namespace `devops` when absent, then sends a merge patch adding `<epoch>-<sha256[:8]>` holding a single JSON line (`time`, `changed_settings`, `data_sha256`, optional commit and reason) and deletes entries older than 30 days.
- **Telemetry log record:** after `kubectl apply` and the history patch succeed, deploy-stack logs `configmap_changed` at `WARNING` on logger `devops_cli.k8s.configmap` so `OTelLoggingHandler` exports the change attributes to Loki.
- **Seven-day query:** run this command to list the changes of the last 7 days with setting names only:

```bash
kubectl -n devops get configmap devops-cli-config-changes -o json | jq -r '.data[] | fromjson | select((.time | fromdateiso8601) >= (now - 604800)) | [.time, (.changed_settings | join(","))] | @tsv'
```

The budget counts what GitHub counts against the rate limit of the installation: a conditional request that GitHub answers with 304 (#3497) leaves the budget when its answer comes. A request with no answer stays in it, because GitHub may have counted it, and a gh command has no status to read. `devops_cli_github_requests_total` still counts every request with its `status`, so `sum(increase(devops_cli_github_requests_total{job="roadmap-service", status!="304"}[1h]))` is the budget's measure (#3939).

The cluster Jobs act as the same App as the Service, and they do not count in `service.github_requests_per_hour`. Only the Service keeps this budget, in a record on its volume. A Job pod has no budget and an `emptyDir` home, so the Service does not see the requests of a Job. GitHub counts the requests of both against the one rate limit of the App installation. To read the requests of the Jobs, set the variable `Job` of the `devops-cli Telemetry` dashboard to `devops-cli-job` or `roadmap-implement`, and read the row GitHub API. The list of the variable follows the time range of the dashboard. If the list does not show this value, no Job ended or sent a request in that range: make the range wider.

The row Roadmap Service of that dashboard charts the rounds, the budget, the queues, the stops and the inputs of the Service.

The rest of ConfigMap `devops-cli-config` (gateway URL, models, context windows, telemetry) comes from `configmap.example.yaml` of the product base that deploy-stack reads (`--product-dir`, default `k8s/devops` of the current checkout), so run it from a checkout of `main`, the revision the cluster runs.

On a cluster that Argo CD manages, the hosts are patches of the Applications. `k8s/README.md` of dan-petty/homelab (Homelab Values at Deploy Time) gives the rules of these patches.

#### When a pull request merges into `main`

1. The Applications track `main`. A pull request here that adds, removes, renames or reorders an Ingress, an IngressRoute or a host in `k8s/devops`, or that adds or changes a value there that holds the placeholder domain, needs a change of the patch in the infra repo. Merge the two close together: until both are in, the Application shows the ComparisonError `testing value <pointer> failed` and its live Ingresses stay as they were. When a pull request changes `k8s/devops/configmap.example.yaml`, run `devops k8s deploy-stack --stack devops` after the merge, because the ConfigMap follows only deploy-stack.
2. Merge. Argo CD builds `main`.
3. The service image changes only with a release. When the release pull request merges, the `Release` workflow's run on `main` builds the service image and pushes it by digest, smoke-tests, scans and attests that digest, then tags it with the release tag and `latest` ([`RELEASE_CYCLE.md`](../RELEASE_CYCLE.md)). Within one poll of `latest` moving, Image Updater puts the `devops` Application on the new digest ([docs/CLUSTER.md](../docs/CLUSTER.md#service-image-updates), Service Image Updates), and roadmap-service rolls with a surge release, so its old pod takes the webhooks until the new pod is ready. Until then both workloads keep the previous release's digest: the merge's own sync changes no image, and nothing is committed. A person who re-runs a failed publish job moves both tags when it passes, and Image Updater rolls the workloads onto the new digest.
4. Check: `devops argo cd apps status devops` and `devops argo cd apps status ingress` are Synced and Healthy and exit 0. For `devops`, the command also reads the digest that `service:latest` names in GHCR and exits 1 when the Application's `spec.source.kustomize.images` pins another one, so ImageUpdater `devops` stopped updating ([docs/CLUSTER.md](../docs/CLUSTER.md#service-image-updates), Service Image Updates). `kubectl get ingress,ingressroute -A -o yaml | grep example.com` prints nothing, and `kubectl -n devops get configmap devops-cli-config -o yaml` holds the configured repositories and the template values of `main` (gateway URL, models, context windows).

### Bootstrap & Adoption

To bootstrap GitOps on a running cluster, use the bootstrap file of a checkout of `main` of dan-petty/homelab (`<homelab-checkout>`):

```bash
git -C <homelab-checkout> pull --ff-only origin main
devops argo cd apps bootstrap-gitops --root-app <homelab-checkout>/k8s/argocd/bootstrap/bootstrap.yaml

# From a checkout of main of this repository:
# Once the Applications devops and ingress exist, set the homelab hosts and ConfigMap
kubectl -n argocd get application devops ingress
devops k8s deploy-stack --stack devops --k8s-dir <homelab-checkout>/k8s

# Once the Applications have synced, retire the Helm release records of the charts they adopted
devops argo cd apps retire-helm-records            # the plan: it reads only
devops argo cd apps retire-helm-records --confirm
```

A chart that `helm upgrade --install` deployed before Argo CD adopted it keeps its Helm release records: Secrets labelled `owner=helm`, such as `sh.helm.release.v1.prometheus.v48`. Argo CD only renders a chart with `helm template`, so `helm list` still shows the release as `deployed`, and `helm rollback` or `helm uninstall` would act on objects that Argo CD owns. `retire-helm-records` deletes the records of a release when an Application renders it and Argo CD applied each of its top-level objects: the object carries the Application's tracking id, or names the field manager `argocd-controller` (Argo CD writes no tracking id on a CustomResourceDefinition). Every object stays. For a release that does not qualify, the plan names each object that Argo CD did not apply; sync that Application, then run the command again. A record with an owner reference, such as those of the Alloy operator, stays. Argo CD shows a record that is left over as an orphaned resource.

### Recovery

When Argo CD is not available, follow `k8s/README.md` of dan-petty/homelab (Recovery): it installs Argo CD with Helm again, with the chart version and the values of the environment. Then do the steps of [Bootstrap & Adoption](#bootstrap--adoption).

### Drift Detection & Sync Commands

Inspect and manage GitOps state using native `devops argo` commands:

```bash
# List all managed Applications and their sync/health statuses
devops argo cd apps list

# Check detailed status of an Application
devops argo cd apps status <app-name>

# Manually trigger reconciliation / sync for an Application
devops argo cd apps sync <app-name>
```

### Pausing an Application

Every Application sets `enabled: true` under `spec.syncPolicy.automated` in git. The value is in the parent's last-applied configuration, so a different value in the cluster is drift. `cluster` is the parent of the Applications in `argocd/apps/` of the environment tree, and `bootstrap` is the parent of `cluster` and of itself.

- Pause an Application in git: set `enabled: false` in its manifest in dan-petty/homelab and merge the change. While it is paused, the `ArgoCdAutoSyncDisabled` alert fires after 15 minutes.
- Do not pause an Application in the Argo CD UI or API. Its parent shows it OutOfSync and turns automated sync on again at its next self-heal.
- For an emergency stop that cannot wait for a merge, or for a volume move (Local-Path Volume Placement), pause from the top down: `bootstrap`, then `cluster`, then the Application. A paused `bootstrap` does not revert itself. Then commit the pause, or turn `bootstrap` on again: it restores `cluster`, and `cluster` restores the others from git.

## The Kubernetes API at `k8s.<domain>`

Off the home network, `kubectl` reaches the API server through the tunnel as a TCP route. An HTTP hostname cannot carry it: Cloudflare ends TLS at its edge, which drops kubectl's client certificate. `cloudflared access tcp` on the workstation carries the connection to the edge after an Access login, and TLS stays end to end between kubectl and the API server.

1. Route the hostname to the API server. `tunnel sync` merges into the tunnel's configuration and places a new hostname ahead of any wildcard rule that would take its traffic (cloudflared uses the first rule that matches). Use a hostname an Access application covers: `devops cloudflare access status` lists them, and `devops cloudflare access sync --domain k8s.<domain> -e <email>` adds one.
   ```bash
   devops cloudflare tunnel sync --subdomains k8s --service tcp://kubernetes.default.svc.cluster.local:443 --dry-run
   devops cloudflare tunnel sync --subdomains k8s --service tcp://kubernetes.default.svc.cluster.local:443
   ```
   `cloudflared/networkpolicy.yaml` of the environment tree lets cloudflared reach the API server on 6443. `k8s/README.md` of dan-petty/homelab (Cloudflare Wildcard Tunnel & Ingress Routing) tells how to set up the tunnel and its Access application.
2. On the workstation, install `cloudflared` (the devtools image holds it), set the hostname of the route, and start the forward. `devops k8s tunnel start` runs `cloudflared access login` first: it opens a browser for the Access login or prints the login URL, and stores the token without printing it. Then it starts `cloudflared access tcp` in the background on `127.0.0.1:16443` (`--port` sets another port), records it under the data directory and waits until the port accepts connections. When a forward already runs, it reports that forward and starts no other. `--context` adds or updates the kubeconfig cluster and context `<cluster>-tunnel`, with the cluster, the user and the CA data of the home context (`k8s.context`, or `--from-context`), the server `https://127.0.0.1:16443` and the TLS server name `kubernetes.default.svc`.
   ```bash
   devops config set k8s.tunnel_host k8s.<domain>
   devops k8s tunnel start --context
   kubectl --context <cluster>-tunnel get nodes
   ```
3. `devops k8s tunnel status` shows the forward, whether its port accepts connections, and whether the API server of the tunnel context answers. A 401 or a 403 counts as an answer, because the request reached the API server. `devops k8s tunnel stop` stops the forward and its process group. `devops k8s switch-context <cluster>-tunnel` makes the tunnel context the one that `devops k8s` commands use.

## Directory Structure

devops-cli tracks only the product base `k8s/devops` and Markdown documents under `k8s/`. The environment tree is the `k8s/` folder of dan-petty/homelab.

```
k8s/
├── devops/                   # The product base: the in-cluster devops-cli runtime. Application devops and `deploy-stack --product-dir` read it
│   ├── kustomization.yaml    # Its resources; Image Updater sets the service image's digest on Application devops
│   ├── serviceaccount.yaml   # devops-cli service account without an API token
│   ├── configmap.example.yaml # devops-cli config template: deploy-stack renders ConfigMap devops-cli-config from it and config.yaml
│   ├── cronjob.yaml          # Suspended CronJob devops-cli, the template of every cluster job
│   ├── cronjob-runner.yaml   # Suspended CronJob devops-cli-runner, the template of the implement job's runner Job
│   ├── cronjob-stage.yaml    # Suspended CronJob, the template of the stage Job
│   ├── cronjob-repos-drift.yaml # Nightly drift check of the repository settings
│   ├── cronworkflow-rag-ingest.yaml # CronWorkflow rag-ingest: runs WorkflowTemplate rag-ingest every 3 minutes
│   ├── workflowtemplate-rag-ingest.yaml # WorkflowTemplate rag-ingest: keeps the RAG index current
│   ├── cronworkflow-infra-drift.yaml # CronWorkflow infra-drift: runs WorkflowTemplate infra-drift each day
│   ├── workflowtemplate-infra-drift.yaml # WorkflowTemplate infra-drift
│   ├── service-probe.yaml    # Suspended CronJob, the template of the service probe pods
│   ├── networkpolicy.yaml    # Default-deny perimeter: DNS, the gateway and public HTTPS out; skips the crawl4ai, searxng, renovate, planner run and valkey-roadmap pods. Lets each Argo Workflow pod reach the API server on TCP 6443
│   ├── networkpolicy-infra.yaml # Lets the infra pods reach the cluster nodes on TCP 22
│   ├── networkpolicy-rag-ingest.yaml # Lets the rag-ingest pods reach Qdrant on TCP 6333
│   ├── alerts/
│   │   └── inbox.yaml        # PrometheusRule of the person causes of the roadmap
│   ├── dashboards/           # The product dashboards. The environment takes this folder as a remote base, so the kustomization above does not list it
│   │   ├── kustomization.yaml # configMapGenerator: ConfigMap grafana-devops-cli-dashboards in namespace monitoring
│   │   ├── devops-cli.json   # devops-cli commands, reviews, RAG, spend and the roadmap Service
│   │   ├── devops-ai-rag.json # AI and RAG metrics
│   │   ├── ai-spend.json     # AI spend and LLM usage
│   │   ├── project-metrics.json # Project and engineering velocity, release cadence and CI pass rates
│   │   └── roadmap-service-telemetry.json # Roadmap Service telemetry
│   ├── monitoring/
│   │   ├── prometheus-rules-values.yaml # The product alert and recording rules, a Helm values file of prometheus-community/prometheus
│   │   └── slos/             # One Sloth spec for each SLO of the product
│   ├── crawl4ai/             # Crawl4AI page-text service: Deployment, Service and the NetworkPolicies of the pod and of its one client
│   ├── mcp-server/           # Role-scoped MCP server: Deployment, Service and NetworkPolicies for the roadmap Service and the Job pods
│   ├── searxng/              # SearXNG search service: settings ConfigMap, Deployment, Service, ServiceMonitor and NetworkPolicies
│   ├── valkey-roadmap/       # valkey-roadmap, the store of the shared state of the roadmap jobs: the Valkey base of dan-petty/infra at a release tag
│   │   ├── kustomization.yaml # The base, its three components, the name suffix and the patches of this store
│   │   └── valkey.conf       # The settings: an append-only file, and no eviction
│   └── roadmap-service/      # Continuous roadmap service Deployment, Service, Ingress, rate-limit Middleware, NetworkPolicies, PVC, ServiceAccount, Role, admission policy and the suspended planner run CronJob
└── README.md                 # This file
```

## Roadmap Service metrics

The roadmap Service serves its counters on the `/metrics` route of the deployment. [Roadmap service](../docs/CLUSTER.md#roadmap-service) lists each counter with its labels.
