# Design

## Overview

The `devops argo workflows logs` command streams pod logs for execution nodes in an Argo Workflow. Argo Workflows supports two naming schemes for execution pods:
- `v1`: The pod name equals the internal node identifier (`node.id`).
- `v2` (default since v3.4): The pod name follows `<workflow>-<templateName>-<hash>`, where `<hash>` is the decimal representation of the 32-bit FNV-1a hash of the node name. When the entrypoint node name equals the workflow name, the pod name equals the workflow name.

Additionally, pods created by Argo Workflows contain two containers: `wait` (the Argo execution helper) and `main` (the user workload container). The Kubernetes API server requires the client to specify a container name when multiple containers exist in a pod.

## Architecture & Algorithm

### Pod Name Derivation

1. Filter the workflow `status.nodes` map:
   - Select nodes where `type == "Pod"`.
   - Exclude nodes where `phase in ("Skipped", "Omitted")`.
2. Determine naming mode:
   - Inspect workflow metadata annotations for `workflows.argoproj.io/pod-name-format`.
   - If set to `"v1"`, use `v1` derivation.
   - If set to `"v2"` or absent, use `v2` derivation by default.
3. Compute pod name:
   - Under `v1`: Use `str(node.get("id") or node_id)`.
   - Under `v2`:
     - If `node.type == "Container"`: `pod_node_name = re.sub(r"\.[^/.]+$", "", node.name)`
     - Else: `pod_node_name = node.name or node.id`
     - If `workflow_name == pod_node_name`: Pod name is `workflow_name`.
     - Else:
       - `template_name = node.templateName or node.templateRef.template or ""`
       - `prefix = f"{workflow_name}-{template_name}"` if `template_name` else `workflow_name`
       - Ensure prefix length is at most 242 characters (253 minus 10-character hash minus hyphen).
       - Compute `hash_val = fnv32a(pod_node_name)`.
       - Pod name is `f"{prefix}-{hash_val}"`.

### Container Selection & 404 Fallback

1. `workflows_logs` accepts `--container` (`-c`) with default `"main"`.
2. When streaming logs, the CLI queries pods using the resolved version (default `v2`).
3. If fetching logs for a pod raises an HTTP 404 Not Found error and `v2` was used without an explicit version annotation, the command re-evaluates the workflow nodes under `v1` naming and retries.

## Rejected Alternatives

### 1. Read controller ConfigMap in `argo-workflows` namespace

- **Alternative**: Read the `workflow-controller-configmap` in the controller namespace to discover the active `POD_NAMES` setting before listing pods.
- **Evidence for rejection**: Reading ConfigMaps in foreign system namespaces requires cluster-wide or cross-namespace RBAC permissions. Regular users and CI service accounts often have access only to workflow namespaces, not controller configurations. Deriving names from the workflow status and falling back from `v2` to `v1` on 404 requires no additional RBAC permissions.

### 2. Invoke the external `argo` CLI binary

- **Alternative**: Wrap `argo logs <workflow> -c <container>` via subprocess.
- **Evidence for rejection**: DevOps CLI operates natively using `KubernetesService` (CoreV1Api and CustomObjectsApi). Adding an external binary dependency requires the `argo` CLI on host PATH, failing in minimal containers and dev environments where only `kubectl` or `devops` is installed.
