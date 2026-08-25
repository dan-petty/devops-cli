# Kubeconform Tool Reference Manual

## 1. Overview & Operational Mandate
Kubeconform is a high-speed Kubernetes manifest validator based on OpenAPI JSON schemas. It checks whether Kubernetes resource YAML files strictly conform to declared Kubernetes API specifications without requiring a live cluster connection.

In `devops-cli`, Kubeconform is integrated via `devops k8s validate` and `run_kubeconform_validation()` under `src/devops_cli/security/kubeconform.py`.

## 2. Key Capabilities
- **Fast Offline Validation**: Validates manifests against official Kubernetes JSONSchema definitions.
- **Strict Schema Enforcement**: Flags undeclared extra properties and structural anomalies with `--strict`.
- **Target Kubernetes Versions**: Supports arbitrary Kubernetes target versions (`--kubernetes-version 1.30.0`).

## 3. CLI Invocations
```bash
# Validate manifests in current directory against latest schema
devops k8s validate .

# Validate specific deployment file against Kubernetes 1.31.0
devops k8s validate k8s/deployment.yaml --kubernetes-version 1.31.0

# Export validation errors as JSON
devops k8s validate . --json
```

## 4. Native Persona Tool Registration
- **Registered Tool**: `k8s_validate_manifests`
- **Personas**: `devsecops`, `architect`, `qa`
