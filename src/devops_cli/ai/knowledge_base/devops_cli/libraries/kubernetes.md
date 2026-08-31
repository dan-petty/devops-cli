# Code Library: Kubernetes (Python Client SDK)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [github.com/kubernetes-client/python](https://github.com/kubernetes-client/python) |
| **Public Git Repository** | [github.com/kubernetes-client/python](https://github.com/kubernetes-client/python) |
| **Official PyPI Package** | [pypi.org/project/kubernetes](https://pypi.org/project/kubernetes/) (`36.0.3`) |
| **DevOps CLI Integration** | [`src/devops_cli/commands/k8s/`](file:///workspaces/devops-cli/src/devops_cli/commands/k8s/) • [`src/devops_cli/k8s/`](file:///workspaces/devops-cli/src/devops_cli/k8s/) |

---

## 2. General Information & Architecture

The **Kubernetes Python Client** is the official programmatic SDK for the Kubernetes REST API. It communicates with the kube-apiserver using kubeconfig contexts or in-cluster ServiceAccount tokens to manage Workloads, Pods, Services, Namespaces, Secrets, and Custom Resource Definitions (CRDs).

In `devops-cli`:
- **Cluster Diagnostics**: Powers `devops k8s status`, `devops k8s pods`, and `devops k8s rbac-audit`.
- **TLS Secret Management**: Creates and syncs `kubernetes.io/tls` secrets across namespaces (`devops k8s create-tls-secret`).
- **Context Inspection**: Powers `devops k8s contexts` and `devops k8s switch-context`.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Kubernetes SDK |
| :--- | :--- | :--- | :--- |
| **`kubernetes` (Official)** | 100% complete OpenAPI coverage, official support, typed model classes for all K8s objects, robust kubeconfig loader. | Large generated codebase. | **Selected**: The standard, battle-tested Kubernetes SDK across the Python cloud-native industry. |
| **`pykube-ng`** | Lightweight, pythonic syntax for common resources. | Smaller community, incomplete coverage of newer Kubernetes APIs and CRDs. | Rejected: Lacks complete CRD and custom API coverage. |
| **`lightkube`** | Modern async-capable lightweight Kubernetes client. | Less widespread adoption, fewer third-party integrations. | Rejected: Official SDK is required for maximum provider compatibility. |
| **`kubectl` Subprocesses** | Directly invokes `kubectl`. | Overhead of process spawning, fragile JSON parsing, difficult to handle structured errors. | Used selectively for complex porcelain commands (`kubectl port-forward`, `kubectl diff`). |

---

## 4. Key Concepts & Core Patterns

1. **Config Loading**:
   - `config.load_kube_config(context=...)`: Loads local workstation `~/.kube/config`.
   - `config.load_incluster_config()`: Automatically detected when running inside a Pod.
2. **API Client Hierarchy**:
   - `CoreV1Api`: Pods, Services, Namespaces, Secrets, Nodes, ConfigMaps.
   - `AppsV1Api`: Deployments, StatefulSets, DaemonSets.
   - `CustomObjectsApi`: ArgoCD Applications, OpenTelemetry CRDs.
3. **Defensive Error Handling**: Catches `kubernetes.client.exceptions.ApiException` to extract exact HTTP status codes (e.g. 404 Not Found, 409 Conflict).

---

## 5. Common & Advanced Usage Examples

### Listing Running Pods in a Namespace
```python
from kubernetes import client, config


def list_namespace_pods(namespace: str = "default") -> list[dict]:
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pod_list = v1.list_namespaced_pod(namespace=namespace)

    return [
        {
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "ip": pod.status.pod_ip,
            "node": pod.spec.node_name,
        }
        for pod in pod_list.items
    ]
```

### Creating or Updating a Kubernetes TLS Secret
```python
import base64
from kubernetes import client, config


def upsert_tls_secret(namespace: str, secret_name: str, cert_pem: bytes, key_pem: bytes):
    config.load_kube_config()
    v1 = client.CoreV1Api()

    secret_body = client.V1Secret(
        metadata=client.V1ObjectMeta(name=secret_name),
        type="kubernetes.io/tls",
        data={
            "tls.crt": base64.b64encode(cert_pem).decode("utf-8"),
            "tls.key": base64.b64encode(key_pem).decode("utf-8"),
        },
    )
    try:
        v1.create_namespaced_secret(namespace=namespace, body=secret_body)
    except client.exceptions.ApiException as e:
        if e.status == 409:
            v1.replace_namespaced_secret(name=secret_name, namespace=namespace, body=secret_body)
        else:
            raise
```

---

## 6. Best Practices & Security Standards

1. **Lazy SDK Loading**: Import `kubernetes` client dynamically inside subcommands to preserve sub-80ms startup times for unrelated commands.
2. **Identifier Validation**: Validate all namespace and context strings with `_validate_k8s_identifier()` to prevent shell escape and injection attacks.
3. **Mask Sensitive Payload Data**: Never log unencrypted Secret payloads in trace spans or CLI output.
