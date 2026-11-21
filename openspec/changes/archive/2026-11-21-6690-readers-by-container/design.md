# Design

## Decisions
- **A read with no name takes the container that runs, else the container that ended the pod.**: The deadline and the live view need the phase that runs, and the report needs the container that failed. One rule in `ClusterJobs` serves each reader, and the readers do not read the pod status themselves.
- **A pod with one container is read whatever the name.**: The one-container template runs every phase in one container, so a reader that names `agent` or `publish` gets the same log as before the switch.
- **The end of a pod is the first container that failed, else the last that ended.**: `prepare` ends with 0 before `agent` starts, so the first terminated container is not the cause.
- **The phase shape is found by the names of the containers.**: `phase_containers` gives the three names only for the init containers [`prepare`, `agent`] and the container [`publish`], which the admission policy of #3700 pins.
- **Only `agent` gets the size of the unit.**: Kubernetes sizes the pod by the largest init container or the sum of the app containers, and `prepare` and `publish` keep the small row of the template.

## Rejected alternatives
- **Each reader reads the pod status and names the container.**: Rejected: five readers would repeat the same rule.
- **Read the log of all containers with `--all-containers`.**: Rejected: a follow of a container that has not started fails, and the report needs one container.
