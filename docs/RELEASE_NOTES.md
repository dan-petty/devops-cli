# Release Notes — devops-cli v0.1.1

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.1.1

### 📊 Human Invalidation Feedback Dataset Exporter
- **`devops ai review export-feedback`**: Queries `.data/reviews/` for review findings marked as `INVALIDATED` during verification (`devops ai review verify`) and exports them into JSONL benchmark datasets for prompt tuning.

### 🎭 Repository-Level Custom Team Personas
- **`.devops/personas/<name>.md`**: Supports custom reviewer persona prompt overrides defined in target repositories under `.devops/personas/`, loaded dynamically via `load_custom_repo_persona`.

### 🔑 Headless CI Ephemeral Memory Keyring Auth
- **`devops config auth-headless`**: Provides an in-memory fallback secret store (`_EPHEMERAL_CI_SECRETS`) allowing headless Linux CI runners without DBus/SecretService to securely pass session tokens.

### 💬 GitHub PR Inline Commenting
- **`GitHubClient.create_pr_review_comment`**: Line-level inline review comment posting capabilities on pull request diff hunks.

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
