# DevOps CLI Tool Cheatsheets & Command Translation Guide

`devops-cli` provides unified, multi-engine workstation automation that wraps, enhances, and orchestrates common DevOps command-line tools into high-reliability, security-hardened workflows.

This cheatsheet directory maps standard industry tools directly to their `devops-cli` counterparts, highlighting productivity enhancements, cross-platform safeguards, and automated agentic capabilities.

---

## Tool Cheatsheet Index

| Domain | Underlying Tools | DevOps CLI Subcommands | Cheatsheet Guide |
| :--- | :--- | :--- | :--- |
| **Git & GitHub** | `git`, `gh` | `devops repos`, `devops branches`, `devops pr` | [**Git & GitHub Cheatsheet**](./git_and_github.md) |
| **Kubernetes & Helm** | `kubectl`, `helm`, `kustomize`, `k9s` | `devops k8s`, `devops kustomize` | [**Kubernetes Cheatsheet**](./kubernetes.md) |
| **Containers & Docker** | `docker`, `docker compose`, `podman` | `devops docker` | [**Docker & Containers Cheatsheet**](./docker.md) |
| **Infrastructure as Code** | `terraform`, `tofu` | `devops tf`, `devops tofu` | [**Infrastructure as Code Cheatsheet**](./infrastructure.md) |
| **Security & Cryptography** | `trivy`, `bandit`, `kube-linter`, `ssh-keygen` | `devops scan`, `devops ssh`, `devops ai review` | [**Security & SSH Cheatsheet**](./security_and_ssh.md) |
| **CI & Quality Gates** | `ruff`, `pytest`, `mypy`, `actionlint` | `devops ci` | [**CI & Quality Gates Cheatsheet**](./ci_and_quality.md) |
| **Observability & GitOps** | `prometheus`, `grafana`, `argocd` | `devops prometheus`, `devops grafana`, `devops argo` | [**Observability Cheatsheet**](./observability.md) |
| **AI, Agents & RAG** | `ollama`, `qdrant`, LLM APIs | `devops ai` (`chat`, `review`, `analyze`, `rag`, `agents`) | [**AI & RAG Cheatsheet**](./ai_and_rag.md) |

---

## Key Advantages Over Raw Tools

1. **Zero-Plaintext Secret Storage**: Sensitive API keys and tokens (GitHub, OpenAI, Anthropic, Grafana) are retrieved securely from the OS Keyring rather than stored in plain text environment variables or dotfiles.
2. **Multi-Repo & Multi-Cluster Batch Automation**: Commands like `devops repos sync` and `devops k8s deploy-stack` execute actions concurrently across whole workspace trees and multi-context clusters.
3. **Agentic Verification & Criteria Scoring**: Code review and static vulnerability scans are automatically verified against live source files and counter-invalidation criteria using multi-persona AI agents.
4. **Built-in Self-Healing & Memory**: Agentic chat and pipeline execution maintain structured conversational memory with automatic size-triggered context summarization.
