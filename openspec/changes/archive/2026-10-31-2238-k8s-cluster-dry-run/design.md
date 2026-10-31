# Design: Dry-Run Classification for Kubernetes Cluster Commands

## Context
Fourteen Kubernetes cluster commands in `devops-cli` do not follow the dry-run rule. Some run external commands and print an echo-only dictionary preview. Others fail with unrecognized option `--dry-run` or fail to execute under `devops --dry-run <cmd>`.

## Architectural Decisions

### 1. Dedicated Kubernetes Plan Builders Module
Create `src/devops_cli/k8s/cluster_plans.py` with pure argument builders and `PlannedRequest` generators for Kubernetes cluster operations:
- Popeye cluster sanitizer command
- Kubeconfig context listing and context switching
- RBAC role and binding lookups
- Pod listing via CoreV1Api
- Pod logs and multi-pod logs via Stern or kubectl
- Security stream logs via Falco probes
- Service port-forward commands
- Service proxy URL requests

### 2. Request Plan Rendering
For commands classified as `request-plan`, dry-run mode returns a structured result or prints formatted planned requests using `render_request_plan`. When `--format json` or `--json` is supplied, commands emit JSON serialization containing the planned requests.

### 3. Local Preview for `k8s port-forward-stop`
`k8s port-forward-stop` receives `--dry-run` and classification `no-external-request`. In dry-run mode, it inspects active daemons using the daemon manager and reports how many daemons it would stop, without sending `SIGTERM` or removing PID records.

### 4. Direct Execution for Purely Local Commands
`k8s gpu-matrix` and `k8s port-forward-status` receive classification `no-external-request` and declare no `--dry-run` flag. The root proxy in `src/devops_cli/main.py` detects this class and runs them directly when the user executes `devops --dry-run k8s <cmd>`.

## Rejected Alternatives

### Alternative 1: Keep Echo Previews (`render_dry_run_result`)
- *Rejected*: The owner dry-run rule (#412) states that dry-run returns planned requests, not arbitrary dictionary summaries or argument echoes. Echo previews hide the real operations that would run.

### Alternative 2: Run Read-Only Kubernetes Client Calls During Dry-Run
- *Rejected*: The owner dry-run rule explicitly states: "dry run should just return the command or request that would be run and a dry run response that is the exact same type as the real return object, not run a thousand api requests as read only". Making real cluster requests during dry run risks slow responses and failure when clusters are unreachable.

### Alternative 3: Execute Popeye Scan in Sandbox During Dry Run
- *Rejected*: Running Popeye against a live cluster executes network queries and consumes system resources. A dry run must perform zero network calls.
