"""Tests for living mental model synthesizer and causal graph distiller (devops ai research model)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from devops_cli.ai.research.mental_model import (
    MentalModelSynthesizer,
    get_mental_model_path,
    load_mental_model,
    render_mental_model_markdown,
    save_mental_model,
    topic_to_slug,
    validate_causal_dag,
)
from devops_cli.ai.research.models import (
    CausalEdge,
    CausalGraph,
    CausalNode,
    InvariantRule,
    MentalModel,
    StateTransition,
)
from devops_cli.config.constants import (
    CONST_CAUSAL_NODE_TYPES,
    CONST_CAUSAL_RELATIONSHIPS,
)
from devops_cli.config.defaults import DEFAULT_AI_RESEARCH_DIR
from devops_cli.main import app

runner = CliRunner()


class FakeMentalModelClient:
    """Deterministic fake LLM client returning structured mental models."""

    def __init__(self, canned_model: MentalModel | None = None) -> None:
        self.canned_model = canned_model or MentalModel(
            topic="k8s_reconciler",
            revision=1,
            created_at="2026-10-11T20:00:00Z",
            updated_at="2026-10-11T20:00:00Z",
            summary="Kubernetes controller reconciliation loop model.",
            state_transitions=[
                StateTransition(
                    from_state="Idle",
                    trigger="WatchEvent",
                    to_state="Reconciling",
                    condition="ResourceGenerationChanged",
                ),
                StateTransition(
                    from_state="Reconciling",
                    trigger="StatusUpdated",
                    to_state="Idle",
                    condition="NoConflict",
                ),
            ],
            causal_graph=CausalGraph(
                nodes=[
                    CausalNode(id="N1", label="Spec mutation", node_type="cause"),
                    CausalNode(id="N2", label="Reconciliation queue", node_type="mediator"),
                    CausalNode(id="N3", label="Cluster state convergence", node_type="outcome"),
                ],
                edges=[
                    CausalEdge(source="N1", target="N2", relationship="triggers", confidence=0.95),
                    CausalEdge(source="N2", target="N3", relationship="causes", confidence=0.90),
                ],
            ),
            invariants=[
                InvariantRule(
                    id="INV-1",
                    description="Reconciler must be idempotent",
                    predicate="reconcile(state) == reconcile(reconcile(state))",
                ),
            ],
        )
        self.calls: list[dict[str, Any]] = []

    def chat_structured(
        self,
        system: str,
        prompt: str,
        schema: type[Any],
        **kwargs: Any,
    ) -> Any:
        self.calls.append({"system": system, "prompt": prompt, "schema": schema, **kwargs})
        return self.canned_model


def test_mental_model_constants_and_defaults() -> None:
    expected_nodes = ("cause", "effect", "mediator", "outcome")
    expected_relationships = ("causes", "inhibits", "triggers", "mediates")
    assert (CONST_CAUSAL_NODE_TYPES, CONST_CAUSAL_RELATIONSHIPS) == (
        expected_nodes,
        expected_relationships,
    )
    assert DEFAULT_AI_RESEARCH_DIR == ".data/research"


def test_topic_to_slug() -> None:
    assert (
        topic_to_slug("Kubernetes Reconciler Loop!"),
        topic_to_slug("  ETCD / Raft Consensus  "),
        topic_to_slug("---"),
    ) == (
        "kubernetes_reconciler_loop",
        "etcd_raft_consensus",
        "default",
    )


def test_get_mental_model_path_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    path = get_mental_model_path("K8s Controller")
    assert (path.parent.name, path.name) == ("research", "mental_model_k8s_controller.yaml")


def test_state_transition_validation_and_alias() -> None:
    st = StateTransition.model_validate(
        {
            "from": "Pending",
            "trigger": "Start",
            "to": "Running",
            "condition": "Healthy",
        }
    )
    assert (st.from_state, st.trigger, st.to_state, st.condition) == (
        "Pending",
        "Start",
        "Running",
        "Healthy",
    )
    dumped = st.model_dump(by_alias=True)
    assert (dumped["from"], dumped["to"], dumped["trigger"]) == ("Pending", "Running", "Start")


def test_causal_graph_dag_and_cycle_breaking() -> None:
    nodes = [
        CausalNode(id="A", label="A", node_type="cause"),
        CausalNode(id="B", label="B", node_type="mediator"),
        CausalNode(id="C", label="C", node_type="outcome"),
    ]
    # Edge A->B, B->C is acyclic; adding C->A forms a cycle and must be broken
    edges = [
        CausalEdge(source="A", target="B", relationship="causes"),
        CausalEdge(source="B", target="C", relationship="causes"),
        CausalEdge(source="C", target="A", relationship="causes"),
    ]
    graph = CausalGraph(nodes=nodes, edges=edges)
    validated = validate_causal_dag(graph)
    assert (len(validated.nodes), len(validated.edges)) == (3, 2)
    assert tuple((e.source, e.target) for e in validated.edges) == (("A", "B"), ("B", "C"))


def test_invariant_rule_validation() -> None:
    inv = InvariantRule(
        id="INV-01",
        description="Transactions are atomic",
        predicate="commit(tx) in {Success, Aborted}",
    )
    assert (inv.id, inv.description, inv.predicate) == (
        "INV-01",
        "Transactions are atomic",
        "commit(tx) in {Success, Aborted}",
    )

    with pytest.raises(ValidationError):
        InvariantRule.model_validate({"id": "INV-1"})


def test_mental_model_serialization_round_trip() -> None:
    fake_client = FakeMentalModelClient()
    model = fake_client.canned_model
    data = model.model_dump(by_alias=True)
    yaml_text = yaml.safe_dump(data, sort_keys=False)
    loaded = yaml.safe_load(yaml_text)
    reconstituted = MentalModel.model_validate(loaded)
    assert (
        reconstituted.topic,
        reconstituted.revision,
        len(reconstituted.state_transitions),
        len(reconstituted.causal_graph.nodes),
        len(reconstituted.invariants),
    ) == (
        "k8s_reconciler",
        1,
        2,
        3,
        1,
    )


def test_save_and_load_mental_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    fake = FakeMentalModelClient()
    saved_path = save_mental_model(fake.canned_model)
    assert saved_path.is_file()

    loaded = load_mental_model("k8s_reconciler")
    assert loaded is not None
    assert (loaded.topic, loaded.revision) == ("k8s_reconciler", 1)

    assert load_mental_model("nonexistent_topic") is None


def test_mental_model_synthesizer_empty_inputs_raise() -> None:
    synth = MentalModelSynthesizer()
    with pytest.raises(ValueError, match="Topic must not be empty"):
        synth.synthesize("   ", "Some observations")
    with pytest.raises(ValueError, match="Observations must not be empty"):
        synth.synthesize("topic", "   ")


def test_mental_model_synthesizer_progressive_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    fake_client = FakeMentalModelClient()
    synth = MentalModelSynthesizer(client=fake_client)

    # Revision 1
    rev1 = synth.synthesize("k8s_reconciler", "Initial observations")
    assert (rev1.topic, rev1.revision) == ("k8s_reconciler", 1)

    # Revision 2: progressively builds on revision 1
    rev2 = synth.synthesize("k8s_reconciler", "Added retry observations", existing_model=rev1)
    assert (rev2.topic, rev2.revision, rev2.created_at) == (
        "k8s_reconciler",
        2,
        rev1.created_at,
    )
    assert len(fake_client.calls) == 2
    assert "Prior Mental Model (Revision 1)" in fake_client.calls[1]["prompt"]


def test_render_mental_model_markdown() -> None:
    fake = FakeMentalModelClient()
    md = render_mental_model_markdown(fake.canned_model)
    assert "# Mental Model: k8s_reconciler" in md
    assert "**Revision**: 1" in md
    assert "State Machine Transitions" in md
    assert "Reconciler must be idempotent" in md
    assert "Causal Graph (DAG)" in md


def test_cli_model_help() -> None:
    result = runner.invoke(app, ["ai", "research", "model", "--help"])
    assert result.exit_code == 0
    assert "Progressively synthesize and distill research observations" in result.output


def test_cli_model_dry_run() -> None:
    result = runner.invoke(
        app,
        ["ai", "research", "model", "cache_invalidation", "-o", "TTL expires", "--dry-run"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output.split("Command response:\n")[1])
    assert (data["status"], data["details"]["topic"]) == ("DRY_RUN", "cache_invalidation")


def test_cli_model_missing_observations_and_no_existing_model_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    result = runner.invoke(app, ["ai", "research", "model", "unknown_topic"])
    assert result.exit_code == 1
    assert "No existing mental model found" in result.output


def test_cli_model_happy_path_creates_file_and_shows_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    fake_client = FakeMentalModelClient()
    monkeypatch.setattr(
        "devops_cli.ai.research.mental_model.get_llm_client",
        MagicMock(return_value=fake_client),
    )

    result = runner.invoke(
        app,
        ["ai", "research", "model", "consensus", "--observations", "Leader election via Raft"],
    )
    assert result.exit_code == 0
    model_path = tmp_path / ".data" / "research" / "mental_model_consensus.yaml"
    assert model_path.is_file()
    loaded = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    assert (loaded["topic"], loaded["revision"]) == ("consensus", 1)


def test_cli_model_with_file_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    fake_client = FakeMentalModelClient()
    monkeypatch.setattr(
        "devops_cli.ai.research.mental_model.get_llm_client",
        MagicMock(return_value=fake_client),
    )

    notes_file = tmp_path / "notes.txt"
    notes_file.write_text("Discovered 503 retry storm on cache stampede\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["ai", "research", "model", "stampede", "--file", str(notes_file)],
    )
    assert result.exit_code == 0
    assert (tmp_path / ".data" / "research" / "mental_model_stampede.yaml").is_file()


def test_cli_model_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    result = runner.invoke(
        app,
        ["ai", "research", "model", "stampede", "--file", str(tmp_path / "missing.txt")],
    )
    assert result.exit_code == 1
    assert "Observations file not found" in result.output


def test_cli_model_show_existing_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    fake = FakeMentalModelClient()
    save_mental_model(fake.canned_model)

    result = runner.invoke(
        app,
        ["ai", "research", "model", "k8s_reconciler", "--show", "--format", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert (payload["topic"], payload["revision"]) == ("k8s_reconciler", 1)


def test_cli_model_format_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    fake = FakeMentalModelClient()
    save_mental_model(fake.canned_model)

    result = runner.invoke(
        app,
        ["ai", "research", "model", "k8s_reconciler", "--show", "--format", "markdown"],
    )
    assert result.exit_code == 0
    assert "# Mental Model: k8s_reconciler" in result.output
    assert "State Machine Transitions" in result.output


def test_cli_model_progressive_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    fake_client = FakeMentalModelClient()
    monkeypatch.setattr(
        "devops_cli.ai.research.mental_model.get_llm_client",
        MagicMock(return_value=fake_client),
    )

    # First run: revision 1
    res1 = runner.invoke(app, ["ai", "research", "model", "cluster", "-o", "Obs 1"])
    assert res1.exit_code == 0
    model1 = load_mental_model("cluster")
    assert model1 is not None and model1.revision == 1

    # Second run: revision 2
    res2 = runner.invoke(app, ["ai", "research", "model", "cluster", "-o", "Obs 2"])
    assert res2.exit_code == 0
    model2 = load_mental_model("cluster")
    assert model2 is not None and model2.revision == 2


def test_cli_model_synthesis_failure_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    failing_client = MagicMock()
    failing_client.chat_structured.side_effect = RuntimeError("Inference timeout")
    monkeypatch.setattr(
        "devops_cli.ai.research.mental_model.get_llm_client",
        MagicMock(return_value=failing_client),
    )

    result = runner.invoke(app, ["ai", "research", "model", "fail_topic", "-o", "bad"])
    assert result.exit_code == 1
    assert "Mental model synthesis failed: Inference timeout" in result.output
