# DevOps CLI Command Surface Reference

This document provides an overview of the main command groups implemented in `devops-cli`. The `project_digest` tool provides authoritative command tree facts from code at run time. The complete generated reference is docs/CLI_REFERENCE.md (`devops docs generate`).

---

## Command Groups Overview

| Group | Subcommand |
| :--- | :--- |
| **`ai`** | `devops ai review branch` |
| | `devops ai review path` |
| | `devops ai review pr` |
| | `devops ai review findings` |
| | `devops ai review verify` |
| | `devops ai review benchmark` |
| | `devops ai review export-feedback` |
| | `devops ai review stats` |
| | `devops ai chat` |
| | `devops ai repomap` |
| | `devops ai diagram` |
| | `devops ai test-gen` |
| | `devops ai rag index` |
| | `devops ai rag query` |
| | `devops ai cache status` |
| | `devops ai cache clear` |
| **`k8s`** | `devops k8s bootstrap` |
| | `devops k8s deploy-stack` |
| | `devops k8s teardown-stack` |
| | `devops k8s contexts` |
| | `devops k8s switch-context` |
| | `devops k8s status` |
| | `devops k8s pods` |
| | `devops k8s apply` |
| | `devops k8s logs` |
| | `devops k8s lint` |
| | `devops k8s audit` |
| | `devops k8s check-deprecated` |
| | `devops k8s enable-tls` |
| **`kustomize`** | `devops kustomize build` |
| | `devops kustomize diff` |
| **`tf`** | `devops tf init` |
| | `devops tf plan` |
| | `devops tf apply` |
| | `devops tf output` |
| | `devops tf destroy` |
| | `devops tf notify-plan` |
| **`scan`** | `devops scan trivy` |
| | `devops scan secrets` |
| | `devops scan sast` |
| | `devops scan report` |
| **`uv`** | `devops uv sync` |
| **`repos`** | `devops repos clone-org` |
| | `devops repos sync` |
| | `devops repos list` |
| **`workspace`** | `devops workspace generate` |
| | `devops workspace add` |
| | `devops workspace remove` |
| **`branches`** | `devops branches list` |
| | `devops branches clean` |
| **`pr`** | `devops pr list` |
| | `devops pr view` |
| | `devops pr check-readiness` |
| | `devops pr create` |
| | `devops pr ready` |
| **`docker`** | `devops docker images` |
| | `devops docker stats` |
| | `devops docker prune` |
| **`argo`** | `devops argo cd apps list` |
| | `devops argo sync` |
| **`grafana`** | `devops grafana dashboards list` |
| | `devops grafana dashboards export` |
| **`prometheus`** | `devops prometheus query` |
| | `devops prometheus rules` |
| **`ssh`** | `devops ssh generate` |
| | `devops ssh register` |
| | `devops ssh rotate` |
| | `devops ssh audit` |
| **`tls`** | `devops tls ca` |
| | `devops tls cert` |
| | `devops tls homelab` |
| | `devops tls inspect` |
| **`telemetry`** | `devops telemetry status` |
| | `devops telemetry test` |
| | `devops telemetry profile` |
| **`docs`** | `devops docs generate` |
| | `devops docs check` |
| **`config`** | `devops config show` |
| | `devops config get` |
| | `devops config set` |
| | `devops config audit-keys` |
| | `devops config output` |
| **`ci`** | `devops ci` |
| | `devops ci audit` |
| | `devops ci build` |
| | `devops ci mutate` |
| **`serve`** | `devops serve` |
| **`devcontainer`** | `devops devcontainer init` |
| | `devops devcontainer validate` |
