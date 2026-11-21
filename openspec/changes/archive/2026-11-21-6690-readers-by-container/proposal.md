# Proposal: #6690

## Why
#3700 runs the runner Job as three containers: the init containers `prepare` and `agent` and the container `publish`. The Service reads the Job log and the container status as one container, and `build_job` finds only the container `runner`. The readers must reach a Service release before the cluster gets the new template, because Argo CD syncs `k8s/` at merge. Closes #6690.

## What Changes
- `log_tail` takes a container name. With no name, it reads the container that runs, else the container that ended the pod. A pod with one container is read whatever the name.
- `pod_end` reads the init containers first and gives the first container that failed, else the last one that ended. An OOM kill of `agent` keeps the class `oom`.
- The fix-checks row reads the result line from `publish`, then from `prepare`. The stage row names the container of its template. The deadline and the live view read the container that runs.
- `template_container` takes a container name, an init container included. `build_job` gives each phase container its `--phase`, `--work /run/roadmap` and the same environment, and only `agent` the size of the unit.
- `devops k8s run-job` follows each phase container in turn and reads the exit code of each by its name.
- No template under `k8s/` changes.

## Capabilities
- `roadmap-implement-runner`: adds the requirements for the Job builder, the readers and run-job on the phases.

## Impact
- `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/commands/k8s/cluster_jobs.py`, `src/devops_cli/roadmap/fix_checks_row.py`, `src/devops_cli/roadmap/stage/stage_submit.py`.
- The one-container runner template of today works as before.

## Feasibility
`read_pod_log_text` passes keyword arguments to `read_namespaced_pod_log`, which takes `container`. The pod status of the Kubernetes client holds `init_container_statuses` before `container_statuses`. A pod with init containers stays `Pending` until they end, so run-job waits for each container, not for the phase of the pod.

## Existing Tool Considered
Kubernetes and its Python client give the init containers, the status of each container and the log of one container by name. The change uses them and adds no tool.
