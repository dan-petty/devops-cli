---
applies_to:
  - "tool:kubeconform@0.8.*"
sources:
  - "https://github.com/yannh/kubeconform"
reviewed: "2026-10-28"
tags:
  - "kubeconform"
  - "k8s"
  - "kubernetes"
---

# Kubeconform Tool Reference Manual

## 1. Overview & Operational Mandate
Kubeconform is a high-speed Kubernetes manifest validator based on OpenAPI JSON schemas. It checks whether Kubernetes resource YAML files strictly conform to declared Kubernetes API specifications without requiring a live cluster connection.

In `devops-cli`, Kubeconform is integrated via `devops k8s validate` and `run_kubeconform_validation()` under `src/devops_cli/security/kubeconform.py`. `tools.lock` pins kubeconform 0.8.0, and `devops install-tools --tool kubeconform` installs it.

`kubeconform -output json` writes one JSON object, `{"resources": [...]}`. Each resource has `filename`, `kind`, `name`, `version`, `status` and `msg`, and an invalid resource also has `validationErrors`. The adapter gives one HIGH finding at `<manifest>:<Kind>/<name>` for each resource with `statusInvalid` or `statusError`. A resource with `statusValid` or `statusSkipped`, which only `-verbose` lists, is no finding. When kubeconform is not on PATH, the scan is `unavailable` and `devops k8s validate` exits 1: no hand-written check replaces the tool.

kubeconform reads each YAML and JSON file of a directory that it gets. It reports each file that is not a manifest, such as a Helm values file, as `statusError`. Thus the adapter gives kubeconform the path of each manifest of the target that git lists and does not ignore, and no other file. A manifest is a YAML or JSON file with a document that has `apiVersion`. A target with no manifest is `not_applicable`, kubeconform does not start, and `devops k8s validate` exits 1.

Kubeconform reads each schema from `raw.githubusercontent.com` unless `-schema-location` names another place, so a validation needs the network.

## 2. Key Capabilities
- **Validation without a cluster**: Validates manifests against the Kubernetes JSON schemas, with no cluster connection.
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
