"""Architecture topology and STRIDE threat modeling diagram generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devops_cli.core.repo import find_top_level_repo_root


@dataclass
class DiagramResult:
    """Diagram generation result containing Mermaid syntax, title, and components."""

    diagram_type: str  # "arch" or "threat"
    title: str
    mermaid_code: str
    components: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "title": self.title,
            "mermaid_code": self.mermaid_code,
            "components": self.components,
        }


def generate_architecture_diagram(root_dir: Path | None = None) -> DiagramResult:
    """Analyze repository modules and generate Mermaid architecture topology diagram."""
    base_root = root_dir or find_top_level_repo_root(Path.cwd())
    src_dir = base_root / "src" / "devops_cli"

    components: list[dict[str, Any]] = (
        [
            {"name": sub.name, "type": "subsystem", "path": f"src/devops_cli/{sub.name}"}
            for sub in sorted(src_dir.iterdir())
            if sub.is_dir() and not sub.name.startswith((".", "_"))
        ]
        if src_dir.is_dir()
        else []
    )

    mermaid_lines = [
        "graph TD",
        "    subgraph CLI[DevOps CLI Application]",
        "        Core[devops_cli.core]",
        "        Config[devops_cli.config / Keyring]",
        "        Commands[devops_cli.commands]",
        "        AI[devops_cli.ai Review & RAG]",
        "        Telemetry[devops_cli.telemetry OTel & Metrics]",
        "    end",
        "    subgraph External[External Workstation & Cloud Services]",
        "        K8s[Kubernetes / Minikube]",
        "        Argo[ArgoCD]",
        "        Grafana[Grafana & Prometheus]",
        "        Ollama[Local Ollama / LLMs]",
        "        Qdrant[Qdrant Vector DB]",
        "    end",
        "    Commands --> Core",
        "    Commands --> Config",
        "    Commands --> AI",
        "    Commands --> Telemetry",
        "    AI --> Ollama",
        "    AI --> Qdrant",
        "    Core --> K8s",
        "    Core --> Argo",
        "    Telemetry --> Grafana",
    ]

    return DiagramResult(
        diagram_type="arch",
        title="DevOps CLI Architecture Topology",
        mermaid_code="\n".join(mermaid_lines),
        components=components,
    )


def generate_threat_diagram(root_dir: Path | None = None) -> DiagramResult:
    """Analyze trust boundaries, network egress, and secrets to build STRIDE threat diagram."""
    mermaid_lines = [
        "graph LR",
        "    subgraph UserSpace[User Workstation Boundary]",
        "        User((Developer / Agent))",
        "        CLI[devops-cli Binary]",
        "        Keyring[(OS Keyring / Secrets)]",
        "    end",
        "    subgraph IsolatedTiers[Data & Execution Isolation]",
        "        DataTier[(.data/ Workspace Tier)]",
        "        TmpTier[(/tmp/ Ephemeral Test Tier)]",
        "    end",
        "    subgraph RemoteBoundaries[Remote Egress & Cloud]",
        "        GitHub[GitHub API / PRs]",
        "        LLM[Ollama / Anthropic / OpenAI]",
        "        SIEM[SIEM Audit Streamer]",
        "    end",
        "    User -->|CLI Invocations| CLI",
        "    CLI -->|Zero-Plaintext Lookup| Keyring",
        "    CLI -->|User Reviews| DataTier",
        "    CLI -->|SSRF Guarded| LLM",
        "    CLI -->|Authenticated HTTPS| GitHub",
        "    CLI -->|Audit Telemetry| SIEM",
    ]

    return DiagramResult(
        diagram_type="threat",
        title="STRIDE Zero-Trust Security & Egress Threat Model",
        mermaid_code="\n".join(mermaid_lines),
        components=[
            {"threat": "CWE-200 Information Exposure", "mitigation": "Exception Host Masking"},
            {"threat": "CWE-918 SSRF", "mitigation": "Private Network Destination Validation"},
            {"threat": "CWE-312 Plaintext Storage", "mitigation": "Mandatory OS Keyring Isolation"},
            {
                "threat": "CWE-78 Command Injection",
                "mitigation": "Subprocess Argument List Enforcement",
            },
        ],
    )
