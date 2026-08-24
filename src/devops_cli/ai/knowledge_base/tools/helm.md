# Knowledge Base: Helm (Kubernetes Package Manager)

## 1. Overview & Purpose

Helm is the standard package manager for Kubernetes, enabling developers and DevOps teams to define, install, upgrade, and version complex Kubernetes applications using reusable packages called Charts. In the `devops-cli` ecosystem, Helm powers automated stack deployment (`devops k8s deploy-stack`), managing Prometheus, Grafana, ArgoCD, Jaeger, and OpenTelemetry collector charts.

---

## 2. Usage Information & Architecture

- **Chart Repositories & Dependency Management**: Automatically adds and updates upstream Helm repositories (e.g. `prometheus-community`, `grafana`, `argo`, `jaegertracing`).
- **Release Lifecycle Management**: Performs atomic, idempotent release upgrades (`helm upgrade --install`) with wait flags and rollback protection.
- **Values Customization**: Parameterizes deployments via custom YAML values files, configuring resource limits, persistence volumes, and ingress rules.
- **Stack Automation**: Integrated directly into `src/devops_cli/commands/k8s.py` for one-command workstation stack deployments (`devops k8s deploy-stack monitoring`).

---

## 3. Common & Advanced Commands

### DevOps CLI Stack Deployment
```bash
# Deploy all workstation stacks (monitoring, gitops, tracing)
devops k8s deploy-stack all

# Deploy specific monitoring stack (Prometheus & Grafana)
devops k8s deploy-stack monitoring

# Teardown stack cleanly
devops k8s teardown-stack monitoring
```

### Standard & Advanced Helm Commands
```bash
# Add and update Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install or upgrade a release with atomic rollback on failure
helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  --create-namespace \
  --values values.yaml \
  --atomic \
  --timeout 5m0s

# List installed releases across all namespaces
helm list --all-namespaces

# Inspect active user-supplied values of a release
helm get values prometheus -n monitoring

# View complete rendered manifest of a release
helm get manifest prometheus -n monitoring

# Rollback a release to a previous revision
helm rollback prometheus 1 -n monitoring

# Uninstall a release
helm uninstall prometheus -n monitoring
```

---

## 4. Best Practice Guidance

1. **Always Use `--atomic` and `--timeout`**: Using `--atomic` ensures that if deployment fails (e.g. pods fail readiness probes), Helm rolls back automatically to the previous working release state.
2. **Deterministic Chart Versions**: Always lock chart versions (`--version <semver>`) in production scripts rather than pulling floating latest charts.
3. **Template Validation**: Run `helm template <release> <chart> -f values.yaml | kubelinter lint -` to lint generated manifests prior to applying them to live clusters.
4. **Separate Values from Code**: Maintain environment-specific values files (`values-local.yaml`, `values-prod.yaml`) outside core application logic.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Provenance Verification**: Enable chart verification (`--verify`) with GPG keyrings when consuming third-party Helm charts.
- **Sensitive Values**: Never commit plaintext passwords or API keys in `values.yaml` files. Inject sensitive values at deployment time using OS Keyring or sealed secrets.
- **Namespace Isolation**: Always deploy charts into dedicated namespaces (`--namespace <name> --create-namespace`) with restricted Pod Security Standards.

---

## 6. General Standards & Reference Guidelines

- **Chart Standards**: Follow standard Helm chart conventions (`Chart.yaml` apiVersion v2, `templates/`, `values.yaml`).
- **Release Naming**: Use lowercase kebab-case naming for all Helm releases (e.g. `prometheus-stack`, `argocd-server`).

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [helm.sh](https://helm.sh/)
- **Public Git Repository**: [github.com/helm/helm](https://github.com/helm/helm)
- **Artifact Hub (Charts)**: [artifacthub.io](https://artifacthub.io/)
- **DevOps CLI Stack Deployment**: [src/devops_cli/commands/k8s.py](../../../commands/k8s.py)
