"""Living mental model synthesizer and causal graph distiller."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from devops_cli.ai.client import get_llm_client
from devops_cli.ai.research.models import (
    CausalEdge,
    CausalGraph,
    MentalModel,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import DEFAULT_AI_RESEARCH_DIR

_DEFAULT_SYNTHESIS_SYSTEM = (
    "You are a causal reasoning and state machine synthesis engine for software engineering. "
    "Distill research observations into a structured mental model with explicit state transitions, "
    "a causal DAG, and checkable invariant rules."
)


def topic_to_slug(topic: str) -> str:
    """Normalize a topic name into a safe filesystem slug."""
    clean = re.sub(r"[^a-zA-Z0-9_\-]+", "_", topic.strip().lower()).strip("_-")
    return clean or "default"


def get_mental_model_path(topic: str, repo_root: Path | None = None) -> Path:
    """Resolve the storage path for a topic's mental model YAML file."""
    data_dir_env = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if data_dir_env:
        base_dir = Path(data_dir_env)
    elif repo_root:
        base_dir = repo_root / DEFAULT_AI_RESEARCH_DIR
    else:
        base_dir = Path(DEFAULT_AI_RESEARCH_DIR)

    research_dir = base_dir if base_dir.name == "research" else base_dir / "research"
    slug = topic_to_slug(topic)
    return research_dir / f"mental_model_{slug}.yaml"


def load_mental_model(topic: str, repo_root: Path | None = None) -> MentalModel | None:
    """Load an existing mental model YAML file if present."""
    path = get_mental_model_path(topic, repo_root=repo_root)
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return MentalModel.model_validate(data)
    except OSError, yaml.YAMLError, ValidationError:
        return None


def save_mental_model(model: MentalModel, repo_root: Path | None = None) -> Path:
    """Persist a mental model to its designated YAML file."""
    path = get_mental_model_path(model.topic, repo_root=repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(by_alias=True)
    yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    path.write_text(yaml_text, encoding="utf-8")
    return path


def validate_causal_dag(graph: CausalGraph) -> CausalGraph:
    """Ensure the causal graph is a strict DAG, breaking any detected cycles."""
    node_ids = {n.id for n in graph.nodes}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    filtered_edges: list[CausalEdge] = []

    for edge in graph.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            continue
        # Test if adding this edge creates a cycle
        adj[edge.source].append(edge.target)
        if _has_cycle(node_ids, adj):
            adj[edge.source].remove(edge.target)
        else:
            filtered_edges.append(edge)

    return CausalGraph(nodes=graph.nodes, edges=filtered_edges)


def _has_cycle_from_node(
    start_node: str,
    adj: dict[str, list[str]],
    visited: dict[str, int],
) -> bool:
    """Traverse graph from start_node and return True if a back-edge is encountered."""
    stack = [(start_node, False)]
    while stack:
        curr, processed = stack.pop()
        if processed:
            visited[curr] = 1
            continue
        if visited.get(curr) == 0:
            return True
        if curr in visited:
            continue
        visited[curr] = 0
        stack.append((curr, True))
        for neighbor in adj.get(curr, []):
            if visited.get(neighbor) == 0:
                return True
            if neighbor not in visited:
                stack.append((neighbor, False))
    return False


def _has_cycle(node_ids: set[str], adj: dict[str, list[str]]) -> bool:
    """Check if directed graph contains a cycle using iterative DFS."""
    visited: dict[str, int] = {}
    return any(_has_cycle_from_node(node, adj, visited) for node in node_ids if node not in visited)


def _build_synthesis_prompt(
    topic: str,
    observations: str,
    existing_model: MentalModel | None,
) -> str:
    """Compose structured prompt for initial synthesis or progressive update."""
    sections = [f"Topic:\n{topic}", f"Research Observations:\n{observations}"]
    if existing_model is not None:
        raw_existing = yaml.safe_dump(existing_model.model_dump(by_alias=True), sort_keys=False)
        sections.append(
            f"Prior Mental Model (Revision {existing_model.revision}):\n{raw_existing}\n"
            "Progressively update and refine the prior model while preserving its established structure."
        )
    return "\n\n".join(sections)


def render_mental_model_markdown(model: MentalModel) -> str:
    """Render a mental model as clean GitHub-flavored markdown."""
    lines: list[str] = [
        f"# Mental Model: {model.topic}",
        "",
        f"- **Revision**: {model.revision}",
        f"- **Created**: {model.created_at}",
        f"- **Last Updated**: {model.updated_at}",
        "",
    ]
    if model.summary:
        lines.extend(["## Summary", "", model.summary, ""])

    lines.extend(["## State Machine Transitions", ""])
    if not model.state_transitions:
        lines.extend(["*No state transitions defined.*", ""])
    else:
        lines.extend(
            [
                "| From State | Trigger | To State | Condition |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for st in model.state_transitions:
            cond = st.condition or "-"
            lines.append(f"| `{st.from_state}` | {st.trigger} | `{st.to_state}` | {cond} |")
        lines.append("")

    lines.extend(["## Causal Graph (DAG)", ""])
    if not model.causal_graph.nodes:
        lines.extend(["*No causal nodes defined.*", ""])
    else:
        lines.extend(["### Causal Nodes", ""])
        for node in model.causal_graph.nodes:
            lines.append(f"- **{node.id}** (`{node.node_type}`): {node.label}")
        lines.append("")

        lines.extend(["### Causal Relationships", ""])
        for edge in model.causal_graph.edges:
            lines.append(
                f"- `{edge.source}` ──[{edge.relationship} (conf: {edge.confidence:.2f})]──> `{edge.target}`"
            )
        lines.append("")

    lines.extend(["## Invariant Rules", ""])
    if not model.invariants:
        lines.extend(["*No invariant rules defined.*", ""])
    else:
        lines.extend(
            [
                "| ID | Invariant Description | Verifiable Predicate |",
                "| :--- | :--- | :--- |",
            ]
        )
        for inv in model.invariants:
            lines.append(f"| `{inv.id}` | {inv.description} | `{inv.predicate}` |")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


class MentalModelSynthesizer:
    """Distills raw research observations into living structured mental models."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def synthesize(
        self,
        topic: str,
        observations: str,
        existing_model: MentalModel | None = None,
        repo_root: Path | None = None,
    ) -> MentalModel:
        """Synthesize or progressively update a mental model from observations."""
        stripped_topic = topic.strip()
        stripped_obs = observations.strip()
        if not stripped_topic:
            raise ValueError("Topic must not be empty.")
        if not stripped_obs:
            raise ValueError("Observations must not be empty.")

        client = self.client or get_llm_client(task="research")
        system_prompt = load_task_prompt("mental_model_synthesis.md") or _DEFAULT_SYNTHESIS_SYSTEM
        user_prompt = _build_synthesis_prompt(stripped_topic, stripped_obs, existing_model)

        res = client.chat_structured(
            system=system_prompt,
            prompt=user_prompt,
            schema=MentalModel,
        )

        # Enforce progressive lineage and timestamp invariants
        now_ts = datetime.now(UTC).isoformat()
        if existing_model is not None:
            new_rev = existing_model.revision + 1
            created_at = existing_model.created_at
        else:
            new_rev = 1
            created_at = now_ts

        valid_dag = validate_causal_dag(res.causal_graph)

        return MentalModel(
            topic=stripped_topic,
            revision=new_rev,
            created_at=created_at,
            updated_at=now_ts,
            summary=res.summary,
            state_transitions=res.state_transitions,
            causal_graph=valid_dag,
            invariants=res.invariants,
        )
