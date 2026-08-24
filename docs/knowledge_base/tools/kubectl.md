# Knowledge Base: kubectl (Kubernetes CLI Orchestrator)

## 1. Overview & Purpose

`kubectl` is the official Kubernetes command-line interface for communicating with the Kubernetes API server (`apiserver`). In the `devops-cli` ecosystem, `kubectl` is utilized to inspect cluster health, query pods across namespaces, stream container logs, manage cluster contexts, and deploy/teardown infrastructure workloads.

---

## 2. Usage Information & Architecture

- **Kubeconfig Resolution**: Automatically reads from `~/.kube/config`, environment variable `KUBECONFIG`, or cluster contexts configured by Minikube.
- **CLI Subcommand Integration**: `devops k8s` provides native commands wrapping `kubectl` operations with telemetry, rich terminal tables, and bounded subprocess execution:
  - `devops k8s pods`: Real-time formatted pod tables with status, restarts, and readiness.
  - `devops k8s status`: Overall cluster connectivity and component status probe.
  - `devops k8s logs`: Streaming container logs with pod selection.
- **Defensive Timeouts**: All programmatic `kubectl` executions enforce explicit timeouts to prevent CLI hangs on unresponsive API endpoints.

---

## 3. Common & Advanced Commands

### DevOps CLI Kubernetes Subcommands
```bash
# List all pods across all namespaces in a formatted table
devops k8s pods --all-namespaces

# List pods in a specific namespace with watch mode
devops k8s pods -n monitoring -w

# Check overall Kubernetes cluster connectivity and node health
devops k8s status

# Stream logs from a specific pod
devops k8s logs -n monitoring -l app.kubernetes.io/name=prometheus --tail 50
```

### Standard & Advanced `kubectl` Commands
```bash
# Get nodes with wide output (IPs, OS images, kernel versions)
kubectl get nodes -o wide

# Describe pod events and container termination reasons
kubectl describe pod <pod_name> -n <namespace>

# Execute an interactive command inside a pod container
kubectl exec -it <pod_name> -n <namespace> -c <container_name> -- /bin/sh

# Port-forward a cluster service to local port
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Output resource definitions as clean YAML
kubectl get deployment my-app -n default -o yaml

# Top nodes and pods resource usage (CPU / Memory)
kubectl top nodes
kubectl top pods --all-namespaces
```

---

## 4. Best Practice Guidance

1. **Explicit Namespaces**: Always specify explicit namespaces (`-n <namespace>`) rather than relying on default contexts to prevent accidental operations in the wrong namespace.
2. **Label Selectors**: Use standard Kubernetes recommended labels (`app.kubernetes.io/name`, `app.kubernetes.io/instance`, `app.kubernetes.io/version`) when filtering resources (`-l app.kubernetes.io/name=grafana`).
3. **Structured Output for Automation**: When writing scripts or tools, use `-o json` or `-o jsonpath` instead of parsing plain text column output.
4. **Dry-Run Validation**: Validate manifests against the live API server using `kubectl apply -f manifest.yaml --dry-run=server` before executing live state changes.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Kubeconfig File Permissions**: Ensure `~/.kube/config` is protected with strict `0600` file permissions (`chmod 600 ~/.kube/config`).
- **RBAC Least Privilege**: Never grant `cluster-admin` privileges to automated developer service accounts unless cluster bootstrap is explicitly required.
- **Sensitive Secrets**: Never inspect or output secret data in plain text logs; always use sanitized outputs.
- **Network Egress Safeguards**: Protect API server credentials from leaking across untrusted child repository subprocesses.

---

## 6. General Standards & Reference Guidelines

- **API Deprecation Audits**: Audit manifests with Pluto and KubeLinter before deploying across Kubernetes versions.
- **Context Switching**: Use `kubectl config get-contexts` and `kubectl config use-context <name>` to verify target clusters before applying mutations.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [Kubernetes kubectl Reference](https://kubernetes.io/docs/reference/kubectl/)
- **Public Git Repository**: [github.com/kubernetes/kubectl](https://github.com/kubernetes/kubectl)
- **Official Kubernetes Releases**: [dl.k8s.io/release](https://dl.k8s.io/release/)
- **DevOps CLI Kubernetes Engine**: [src/devops_cli/commands/k8s.py](file:///workspaces/devops-cli/src/devops_cli/commands/k8s.py)
