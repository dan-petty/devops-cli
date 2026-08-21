"""Centralized CLI help strings catalog for devops-cli (English)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OptionHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo: str = "Repository root directory (default: current directory)."
    persona: str = "Reviewer persona to activate (devsecops, architect, pm, auditor, qa)."
    all_personas: str = "Run all reviewer personas in sequence."
    base_branch: str = "Base git branch to diff against (default: main)."
    format_type: str = "Output format type (table, json, yaml, markdown)."
    dry_run: str = "Preview execution plan without mutating external state."
    verbose: str = "Enable detailed logging output."
    timeout: str = "Timeout duration in seconds."
    context: str = "Kubernetes cluster context name."
    namespace: str = "Kubernetes namespace."
    output_path: str = "Destination file path for output report or artifacts."


class AICommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot)."
    chat: str = "Interactive multi-turn AI chat session with optional tool execution."
    config: str = "Show or update AI provider configuration (provider, model, endpoints, keys)."
    test: str = "Send a test prompt to verify AI provider connectivity."
    agents: str = "Generate or regenerate AGENTS.md, CLAUDE.md, and copilot-instructions.md."
    review: str = "AI-powered multi-persona code review system."
    analyze: str = "Analyze codebase metadata and generate structural outlines."
    rag: str = "Manage RAG vector embeddings, indexing, and semantic search (Qdrant)."


class K8sCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Manage Kubernetes clusters, pods, services, and workloads."
    pods: str = "List running pods across namespaces with health metrics."
    status: str = "Cluster health and resource utilization summary."
    port_forward: str = "Forward local port to a remote Kubernetes service."


class SSHCommandHelp(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: str = "Generate, rotate, audit, and register Ed25519 SSH keypairs."
    generate: str = "Generate a new Ed25519 SSH keypair with 90-day expiry naming."
    status: str = "Show currently active SSH key and days until expiration."
    audit: str = "Audit SSH key configuration and recommend rotation if near expiry."


class HelpCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    options: OptionHelp = OptionHelp()
    ai: AICommandHelp = AICommandHelp()
    k8s: K8sCommandHelp = K8sCommandHelp()
    ssh: SSHCommandHelp = SSHCommandHelp()


HELP = HelpCatalog()
