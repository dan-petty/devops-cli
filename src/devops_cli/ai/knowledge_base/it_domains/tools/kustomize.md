# Knowledge Base: Kustomize (Declarative Kubernetes Configuration)

## 1. Overview & Purpose

Kustomize is a template-free declarative configuration management engine for Kubernetes. It allows DevOps engineers to customize raw, untemplated YAML manifests for multiple environments (e.g. `development`, `staging`, `production`) using overlays, patches, and resource generators without modifying the original base files.

---

## 2. Usage Information & Architecture

- **Base & Overlay Pattern**: Establishes a shared `base/` directory containing canonical resource manifests and `overlays/<env>/` directories applying environment-specific overrides.
- **GitOps Alignment**: Native engine embedded directly in `kubectl` (`kubectl apply -k`) and natively supported by ArgoCD for continuous delivery reconciliation.
- **CLI Subcommand**: `devops kustomize` provides build validation and manifest compilation commands.

---

## 3. Common & Advanced Commands

### DevOps CLI Kustomize Commands
```bash
# Build and validate Kustomize overlays
devops kustomize build k8s/overlays/dev

# Build and apply Kustomize configuration directly to cluster
devops kustomize apply k8s/overlays/dev
```

### Standard & Advanced `kustomize` Commands
```bash
# Build Kustomize overlay to stdout
kustomize build overlays/production

# Apply Kustomize directory via native kubectl
kubectl apply -k overlays/production

# Validate generated YAML with KubeLinter
kustomize build overlays/production | kubelinter lint -

# Inspect diff between base and generated overlay
diff -u <(kustomize build base) <(kustomize build overlays/production)
```

### Sample `kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: production

namePrefix: prod-

commonLabels:
  app.kubernetes.io/environment: production
  app.kubernetes.io/managed-by: kustomize

images:
  - name: my-app
    newName: ghcr.io/dan-petty/my-app
    newTag: v0.2.0

patches:
  - path: patch-replicas.yaml
```

---

## 4. Best Practice Guidance

1. **Keep Base Clean**: Base manifests must represent standard, minimal configurations without environment-specific hostnames, replica counts, or secrets.
2. **Use Strategic Merge Patches**: Use strategic merge patches for modifying existing resource fields (`replicas`, `resources`, `image`) without rewriting full manifests.
3. **Common Labels**: Enforce `commonLabels` and `commonAnnotations` at the `kustomization.yaml` root level to ensure proper resource attribution.
4. **ConfigMap & Secret Generators**: Leverage `configMapGenerator` and `secretGenerator` with content hashing to trigger rolling updates automatically when configuration data changes.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Secret Generator Protection**: When using `secretGenerator`, avoid committing raw secret values in `kustomization.yaml`. Use `env` files referenced from encrypted secret stores or SealedSecrets.
- **Path Traversal Restrictions**: Ensure overlays only reference relative paths inside the project repository tree.
- **Pre-Deployment Linting**: Pipe Kustomize output through `kubelinter` and `pluto` before applying to live clusters.

---

## 6. General Standards & Reference Guidelines

- **Directory Structure**:
  ```text
  k8s/
  ├── base/
  │   ├── deployment.yaml
  │   ├── service.yaml
  │   └── kustomization.yaml
  └── overlays/
      ├── dev/
      │   └── kustomization.yaml
      └── prod/
          ├── patch-replicas.yaml
          └── kustomization.yaml
  ```
- **Kustomize Versioning**: Use standard `apiVersion: kustomize.config.k8s.io/v1beta1`.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [kubectl.docs.kubernetes.io/guides/introduction/kustomize](https://kubectl.docs.kubernetes.io/guides/introduction/kustomize/)
- **Public Git Repository**: [github.com/kubernetes-sigs/kustomize](https://github.com/kubernetes-sigs/kustomize)
- **DevOps CLI Kustomize Engine**: [src/devops_cli/commands/kustomize.py](../../../../commands/kustomize.py)
