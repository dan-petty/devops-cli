# Kubernetes & Helm Tool Cheatsheet

Compare standard `kubectl`, `helm`, and `kustomize` workflows with unified `devops-cli` multi-context cluster operations, automatic port-forwarding, and stack orchestration.

---

## 1. Stack Deployment & Helm Orchestration

| Action / Goal | Original Command (`kubectl` / `helm`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Deploy Complete DevOps Stack** | `kubectl apply -f ... && helm repo add ... && helm install ...` | `devops k8s deploy-stack --stack all [-c <context>]` | Unified one-command deployment across namespaces (`argocd`, `llm`, `monitoring`, `otel`), automated Helm conflict adoption, and GPU DaemonSet validation. |
| **Deploy Target Sub-Stack** | Multiple manual `helm install` / `kubectl apply` commands | `devops k8s deploy-stack --stack monitoring` | Modular deployment of individual subsystem stacks (`monitoring`, `llm`, `argocd`, `otel`). |
| **Teardown Cluster Stack** | `helm uninstall ... && kubectl delete ns ...` | `devops k8s teardown-stack --stack all [-c <context>]` | Safe multi-stage resource deletion, CRD preservation checks, and namespace cleanup. |
| **Bootstrap Local Cluster** | `minikube start --driver=docker ...` | `devops k8s bootstrap --provider k3d\|minikube` | Pre-configures host port mappings, local container registries, and DevContainer networks. |

---

## 2. Pod Diagnostics, Health & Discovery

| Action / Goal | Original Command (`kubectl`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **List Stack Pods** | `kubectl get pods -A -l app.kubernetes.io/part-of=devops-cli-stack` | `devops k8s pods [-n <namespace>]` | Color-coded status tables highlighting crashloops, restart counts, and container resource limits. |
| **Check Stack Health** | Multiple `kubectl get svc,deploy,ds,statefulsets` | `devops k8s status [-c <context>]` | Complete health audit evaluating DaemonSets (Ollama GPUs), deployments, and ingress reachability. |
| **Auto-Detect Service Endpoints** | `kubectl get svc -A -o jsonpath=...` | `devops k8s configure-urls [-c <context>]` | Discovers cluster IP/NodePort/hostPort targets and automatically updates local `devops config` settings. |

---

## 3. Port-Forwarding & Local Access

| Action / Goal | Original Command (`kubectl`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Port-Forward All Stack Services** | 7+ separate background `kubectl port-forward` commands | `devops k8s port-forward --stack all` | Concurrently forwards ArgoCD (`:8080`), Grafana (`:8030`), Prometheus (`:8090`), Ollama (`:11434`), Open-WebUI (`:3000`), Qdrant (`:6333`), and Valkey (`:6379`). |
| **Port-Forward Single Service** | `kubectl -n monitoring port-forward svc/grafana 8030:80` | `devops k8s port-forward --stack monitoring` | Forwards only monitoring services with automatic collision detection and port binding checks. |

---

## 4. Kustomize Overlay Generation & Build

| Action / Goal | Original Command (`kustomize`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Build Kustomize Overlay** | `kustomize build k8s/overlays/prod` | `devops kustomize build k8s/overlays/prod` | Validates resource schemas, masks sensitive secret literals, and outputs formatted YAML. |
| **Generate Kustomize Overlay** | Manual `kustomization.yaml` boilerplate authoring | `devops kustomize generate --name <app> --image <img:` | Scaffolds standard Kustomize base and environment overlays (`dev`, `staging`, `prod`). |
