# Kubernetes guideline

This guideline sets how a managed project tunes the performance of a Kubernetes cluster and of the workloads that it deploys. It gives the targets, the method, the rules of each area and the rules for agents and jobs. It applies with no change to each managed project. The README of the environment tree of a project holds the decisions of its cluster. These are the targets that it adds, the owner of its node settings and the link to its gap tracker.

Other guidelines share the area. The SRE guideline owns the SLOs, the alerts, the incidents and the dashboards of each service. The agentic jobs guideline owns the attempt, token and time limits of an agentic job. This guideline owns the resources of the cluster: CPU, memory, process IDs, disk, image pulls, runtimes and placement. [The guideline index](index.md) lists each guideline.

## Scope

- **In scope.** The nodes and their kubelet, distribution and containerd settings. The requests, the limits and the probes of each container, the QoS classes, and the placement of pods and volumes. Also the batch Jobs, the runtimes, the image pulls, the storage, the control plane and the controllers.
- **Out of scope.** The devcontainer of a workstation, the runners of CI, and the quality and the cost of a model call (the agentic jobs guideline). A workload that no manifest of the environment tree declares is out of scope too, and a person owns it.
- **Node settings.** The kubelet, distribution and containerd settings of a node live in the infra repo of the project (setting `infra.repos`), not in the environment tree. A gap in them gets an issue in that repository.

## Principles

1. **Measure first.** A change with no value before it and no value after it is not a tuning change. Each value comes from a query that a reader can run again. The before and after values go in the pull request comment or in the project review report, not in a document.
2. **One change at a time.** A measurement step changes one resource of one workload. Measure it, then keep it or revert it. Two changes in one step hide the effect of each. A pull request can hold several values when each value has its own before value and after value.
3. **Reliability before cost.** First find a configuration that works. Then tune down for cost from the measured use.
4. **Standard controls first.** Use the controls of Kubernetes: requests, limits, probes, QoS classes, PriorityClass, RuntimeClass, kubelet eviction and node allocatable. Use an open tool, such as KRR, kube-linter or kubernetes-mixin, before a script of the project.
5. **Utilization, saturation and errors.** Measure each resource by its use, its queue or pressure, and its errors ([USE method](https://www.brendangregg.com/usemethod.html)). The [pressure stall information](https://docs.kernel.org/accounting/psi.html) of a node gives the saturation of its CPU, memory and I/O. The SRE guideline measures each service by the golden signals.

## Targets

Each target names the alert, the report or the check that measures it. The SRE guideline owns the SLOs and their alerts. The README of the environment tree can add a target for its cluster, such as a pod start time.

**Table 1.** The targets.

| ID | Signal | Target | Measured by | Source |
| :--- | :--- | :--- | :--- | :--- |
| T1 | Memory room | The 7-day peak working set of each container is at most 80 % of its memory limit | The KRR report (strategy `simple`), which gives the peak of each container; kube-linter `unset-memory-requirements` for a container with no limit | 25 % room above the peak |
| T2 | Out-of-memory kills | 0 kernel kills of a long-running container in 7 days | `kube_pod_container_status_last_terminated_reason` with reason `OOMKilled` (kube-state-metrics); `node_vmstat_oom_kill` (node-exporter) for a kill that the container status does not show | A kill loses the work in flight |
| T3 | CPU throttling | Under 25 % of the CFS periods of each container are throttled, over 7 days | kubernetes-mixin `CPUThrottlingHigh` | The 25 % line of `CPUThrottlingHigh` |
| T4 | Restarts | 0 restarts in 7 days, other than a rollout or a node reboot | kubernetes-mixin `KubePodCrashLooping` | A restart loses the work in flight |
| T5 | Pending pods | No pod stays Pending for more than 15 minutes | kubernetes-mixin `KubePodNotReady` | The 15 minutes of `KubePodNotReady` |
| T6 | Capacity for one node loss | The memory requests of the pods that can move fit on the Ready nodes that stay after the loss of the largest worker | kubernetes-mixin `KubeMemoryOvercommit` and `KubeCPUOvercommit` | The loss of the largest node, as in `KubeMemoryOvercommit`. The mixin applies that check only to a cluster with 3 or more control-plane nodes, so a smaller cluster runs the same sum as a query. |
| T7 | Node reserve | Each node reserves memory for the system and the kubelet, and has a hard eviction threshold for memory | The kubelet configuration that the node reports (`/api/v1/nodes/<name>/proxy/configz`) | [Reserve Compute Resources for System Daemons](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/) |
| T8 | Disk | The root filesystem of each node is at most 85 % full | `node_filesystem_avail_bytes` (node-exporter); node-mixin `NodeFilesystemSpaceFillingUp` | The kubelet image collection starts at 85 % (`imageGCHighThresholdPercent`) |
| T9 | Evictions | 0 evictions for node pressure in 7 days | `kube_pod_status_reason` with reason `Evicted` (kube-state-metrics); the `Evicted` events | [Node-pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/) |
| T10 | Profiler cost | The mean CPU of the profiler on each node is under 1 % of the CPUs of the smallest node, and its memory meets T1 | `container_cpu_usage_seconds_total` of the profiler container (cAdvisor) | A profiler on each node must cost less than the waste that it finds |

## Method

### The tuning loop

1. **Baseline.** Run the query of the signal over 7 days, or over 20 or more runs of a Job. Put the value and the query in the pull request.
2. **Change.** Change one resource of one workload in git.
3. **Wait.** Wait for the same window, or for the same number of runs.
4. **Measure.** Run the same query again.
5. **Decide.** Keep the change when its signal moves to the target and no other signal of the area gets worse. Else revert it.
6. **Record.** Put the two values and the query in a comment on the pull request. Then read the project review report again. Do not copy a measured value into a document.

Do not tune from one sample. Rule C9 of the [design spec](../DESIGN.md#chart-rules) gives the smallest sample for each percentile. A query reads at most the retention of its store, so a 7-day window needs 7 days of retention or more.

### Tune down from the measured peaks

The agentic jobs guideline finds a working configuration for a job: it doubles each limit of a job under its success target until the job works. This guideline owns the formula that sizes a container from its measured use:

1. A limit never goes above the allocatable memory of the smallest node that can run the pod.
2. When the workload holds its target, tune down from the measured peaks. Set the memory request at or above the p90 of the 7-day peaks of its pods. Set the memory limit so that the highest peak is at most 80 % of it (T1). Change one value in each step.
3. For a long-running container, take the first values from the KRR report. Then prove them with [the tuning loop](#the-tuning-loop).

### Compare two runtimes or two node settings

A runtime or a node setting changes every pod on a node. So it gets an A/B measurement before any workload uses it:

1. Pin both arms to one node with a node selector. Without the pin, an arm can go to a node with more CPUs.
2. Use one image by digest. Pull it on the node before the first timed run.
3. Do at least 5 runs of each arm, in turns, and drop the first run of each arm. Record the other load of the node at each run.
4. Measure the time from create to Ready and to the end. Measure a CPU-bound task, a task with much file I/O, and the memory of the pod.
5. Prove that the CPU limit throttles and that an allocation above the memory limit ends in `OOMKilled`, in each arm.
6. Record the result in the README of the environment tree before a workload uses the runtime or the setting.

## Areas

### Requests, limits and QoS classes

- **Rule.** Each container sets a CPU request, a memory request and a memory limit. The kernel cannot compress memory, so a container with no memory limit can use all the memory of its node. kube-linter `unset-cpu-requirements` and `unset-memory-requirements` find a container with no request or no limit.
- **QoS classes.** Under node pressure, the kubelet first evicts the pods whose use is above their request, by priority and then by the excess. A `BestEffort` pod always has its use above its request ([Node-pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/), [Pod Quality of Service Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)).
- **Stateful pods.** The memory request of a database or a state store is at or above its 7-day peak. Then node pressure evicts a batch pod first.
- **CPU limits.** The CFS quota period is 100 ms. A container at its CPU limit waits for the next period, so a short scrape or a test worker stops for a time. T3 is the guard.

### Probes

- **Readiness.** Each container that serves traffic has a readiness probe. The probe removes the pod from its Service until the pod can answer.
- **Liveness.** A liveness probe checks only that the process can make progress. It does not check a dependency, because a dependency fault then restarts each replica at the same time.
- **Slow start.** A container with a slow start gets a startup probe, not a long initial delay of its liveness probe.
- **Check.** kube-linter `no-readiness-probe` and `no-liveness-probe` find a container with no probe ([Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)).

### Node capacity and placement

- **Priority.** Give the services and the batch Jobs their own PriorityClasses. Then a pending service pod can preempt a batch pod after a node loss ([Pod Priority and Preemption](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/)).
- **One node loss.** T6 applies to the pods that can move. A pod that a node selector holds to one node cannot move, and a pod on a node-local volume cannot move either. Count them apart.
- **Placement by request.** The scheduler places a pod by its requests, not by its limits. Its default score prefers the node with the most free resources (`LeastAllocated`), and that node can be a control-plane node. Keep a pod whose limit is above its request off a node whose allocatable memory is below its limit, with a node affinity.

### Batch Jobs

- **Asynchronous.** Run batch work as a Job or a Workflow, not in the process of a long-running service. The service that starts the Job does not wait for its end. It reads the result later from the status of the Job or from the record that the Job writes.
- **Event-driven.** An event or a schedule starts each Job. An event is a webhook, a message on a queue, or an event source such as [Argo Events](https://argoproj.github.io/argo-events/). A schedule is a CronJob or a CronWorkflow. The Job gets its input from the event and from git, not from the memory of the process that started it.
- **Repeatable.** A trigger can send one event two times, and a retry runs a Job again. A Job that runs again on the same event gives the same result. Give the Job a name from the event id, so that the API server refuses a second Job with the same name (`AlreadyExists`).
- **Bounded.** Each Job sets `activeDeadlineSeconds`, `backoffLimit` and `ttlSecondsAfterFinished` ([Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)). The [Argo Workflows cost guide](https://argo-workflows.readthedocs.io/en/latest/cost-optimisation/) asks for executor requests, pod garbage collection and a TTL for each Workflow.

### Image pull and start time

- **Measure.** Read the pull time from the image pull histogram of the kubelet when the metric pipeline keeps it. Else read it from the `Pulled` events of the kubelet.
- **Pulls in parallel.** With `serializeImagePulls: false` and no `maxParallelImagePulls`, the kubelet pulls images in parallel with no cap. A node with many cold pulls at one time shares its network among them. Set `maxParallelImagePulls` on such a node.

### Storage and disk

- **Disk.** An alert on the root filesystem fires before the line of T8, so a person acts before the kubelet deletes images or evicts pods.
- **Node-local volumes.** A volume of a node-local storage class keeps its pod on its node. Move the volume before the node goes out of service for a long time.

### cgroups, process IDs and kubelet eviction

**Table 2.** The kubelet settings of this guideline, with the defaults of the [kubelet configuration](https://kubernetes.io/docs/reference/config-api/kubelet-config.v1beta1/).

| Setting | Kubernetes default | Rule |
| :--- | :--- | :--- |
| `evictionHard` `memory.available` | `100Mi` | Set it on each node (T7) |
| `evictionHard` `nodefs.available`, `imagefs.available` | 10 %, 15 % | Keep each at or above its default |
| `kubeReserved`, `systemReserved` memory | none | Set both on each node (T7) |
| `podPidsLimit` | -1, no limit | Set it on each node from the peak thread count of its pods |
| `shutdownGracePeriod`, `shutdownGracePeriodCriticalPods` | `0s`, `0s` | Set both, so that a host shutdown gives each pod its drain |
| `serializeImagePulls`, `maxParallelImagePulls` | true, not set | With parallel pulls, set a cap |
| `imageGCHighThresholdPercent`, `imageGCLowThresholdPercent` | 85, 80 | Keep both; T8 uses the high line |
| `mergeDefaultEvictionSettings` | false | Set it to true, or set each eviction threshold |
| `enforceNodeAllocatable` | `pods` | Keep `pods` |

- **Eviction thresholds.** A kubelet that sets one eviction threshold sets each other threshold to 0, unless `mergeDefaultEvictionSettings` is true ([Node-pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)). So a node that sets only a disk threshold has no memory threshold.
- **Reserve.** A node with no memory reserve has an allocatable memory equal to its capacity. Then the pods can take the memory of the system and the kubelet. The Kubernetes guide enforces Allocatable on pods first (`enforceNodeAllocatable: pods`), and enforces `kube-reserved` and `system-reserved` only after monitoring.
- **Process IDs.** With no `podPidsLimit`, one pod can fork until its node has no free process ID. A pod that runs code from a model needs this limit most ([Process ID Limits And Reservations](https://kubernetes.io/docs/concepts/policy/pid-limiting/)).
- **Node shutdown.** With `shutdownGracePeriod` at `0s`, a host shutdown ends each pod with no grace ([Graceful node shutdown](https://kubernetes.io/docs/concepts/cluster-administration/node-shutdown/)). Drain a node before planned work.

### Control plane and controllers

- **API server.** Scrape the API server, and alert on its errors and on its answers of 429.
- **Argo CD.** Keep the processor counts and `timeout.reconciliation` at their defaults while the reconcile time of the Applications stays the same. The [Argo CD high availability guide](https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/) tells when to change them.
- **Exec.** A `kubectl exec` adds its processes to the memory of the container. In a container near its memory limit, an exec can cause the out-of-memory kill of the container (rule R3).

## Rules for agents and jobs

1. **R1. Measure before and after.** Use the window or the run count of [the tuning loop](#the-tuning-loop).
2. **R2. One change at a time.** One measurement step changes one resource of one workload. A pull request can hold several values when each value has its own before value and after value, such as a KRR batch.
3. **R3. No exec near the limit.** Do not run `kubectl exec` in a pod whose working set is above 80 % of its memory limit. Read the metrics, the logs or the manifest instead.
4. **R4. Room above the peak.** Do not set a memory limit below the 7-day peak divided by 0.8. Do not remove a limit.
5. **R5. Runtimes.** A workload uses a new RuntimeClass or node setting only after the README of the environment tree holds its A/B result ([the A/B method](#compare-two-runtimes-or-two-node-settings)).
6. **R6. Node settings.** A gap in a kubelet, distribution or containerd setting gets an issue in the infra repo of the project ([Scope](#scope)). A person changes the hardware of a host.
7. **R7. Probes.** Give each container that serves traffic a readiness probe, and never make a liveness probe check a dependency ([Probes](#probes)).
8. **R8. Batch work.** Run batch work as a Job that an event or a schedule starts. Do not make a service wait for it, and make each Job safe to run again on the same event ([Batch Jobs](#batch-jobs)).

## Queries

Run a PromQL query with `devops prometheus query '<expr>'`. A query that groups by `node` or `instance` prints the names of the hosts. Do not copy those names into a document or an issue.

## Sources

- Kubernetes: [Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/), [Pod Quality of Service Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/), [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/), [Node-pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/), [Reserve Compute Resources for System Daemons](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/), [Process ID Limits And Reservations](https://kubernetes.io/docs/concepts/policy/pid-limiting/), [Runtime Class](https://kubernetes.io/docs/concepts/containers/runtime-class/), [Pod Priority and Preemption](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/), [Graceful node shutdown](https://kubernetes.io/docs/concepts/cluster-administration/node-shutdown/), [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/), [Kubelet Configuration](https://kubernetes.io/docs/reference/config-api/kubelet-config.v1beta1/).
- Argo: [Argo Workflows cost optimisation](https://argo-workflows.readthedocs.io/en/latest/cost-optimisation/), [Argo CD high availability](https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/), [Argo Events](https://argoproj.github.io/argo-events/).
- Tools: [kubernetes-mixin](https://github.com/kubernetes-monitoring/kubernetes-mixin) (`CPUThrottlingHigh`, `KubePodNotReady`, `KubePodCrashLooping`, `KubeMemoryOvercommit`, `KubeCPUOvercommit`), [node-mixin](https://github.com/prometheus/node_exporter/tree/master/docs/node-mixin), [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics), [KRR](https://github.com/robusta-dev/krr), [kube-linter checks](https://docs.kubelinter.io/#/generated/checks).
- Methods: [The USE Method](https://www.brendangregg.com/usemethod.html), [Pressure Stall Information](https://docs.kernel.org/accounting/psi.html), [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/).
