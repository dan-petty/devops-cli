# Release Notes — devops-cli v0.1.4

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.1.4

### 🤖 Default Enhanced AI Metadata Analysis
- **`devops ai analyze`**: Enhanced analysis (pseudocode structural outlines, complexity scoring, UTC ISO timestamps) is now enabled by default across all analysis commands (`path`, `branch`, `pr`). Use `--no-enhanced` to opt out.

### ⚡ Incremental Analysis Caching & Force Update Flag
- **`st_mtime` Caching**: Files whose modification timestamp is prior to their recorded `last_analyzed` ISO timestamp skip redundant LLM queries and reuse existing metadata.
- **`devops ai analyze --update-all` (`-u`)**: Force full metadata regeneration regardless of `last_*` timestamps.

### 🔍 Submodule-Aware Dependency Extraction
- **Python AST & Package Scanners**: Preserves full module and submodule imports (e.g. `pydantic.v2`, `rich.console`, `devops_cli.models.ai`) rather than stripping down to root package names.

### 🧹 Clean Pseudocode Outline Generation
- **Zero Imports & Zero Canned Language**: Strictly excludes all import/from statements and package directives from pseudocode outlines (ensuring dependencies stay in their dedicated metadata field) and eliminates generic template phrases.

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
