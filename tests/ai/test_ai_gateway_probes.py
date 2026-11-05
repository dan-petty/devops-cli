"""Tests for LLM gateway capability probes and evaluation (#595)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.ai.gateway import (
    GatewayRoute,
    GatewayRouter,
    GatewayStatus,
    probe_gateway_liveliness_and_models,
)
from devops_cli.ai.gateway_probes import (
    DeepRecallEvaluator,
    ExplicitProhibitionEvaluator,
    JsonAdherenceEvaluator,
    ToolChoiceEvaluator,
    build_capability_probes,
    score_deployment_probes,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import ValidationError
from tests.web_fakes import StubWeb


def test_json_adherence_evaluator() -> None:
    """Verify JsonAdherenceEvaluator validates 5-field JSON schemas."""
    evaluator = JsonAdherenceEvaluator()
    valid_data = {
        "file": "src/main.py",
        "line": 42,
        "severity": "HIGH",
        "rule_id": "SEC001",
        "description": "Missing authentication guard",
    }
    assert evaluator.evaluate_raw(json.dumps(valid_data)) is True

    # Missing line
    invalid_data = {
        "file": "src/main.py",
        "severity": "HIGH",
        "rule_id": "SEC001",
        "description": "Missing line field",
    }
    assert evaluator.evaluate_raw(json.dumps(invalid_data)) is False

    # Plain non-json text
    assert evaluator.evaluate_raw("Not a json response") is False


def test_tool_choice_evaluator() -> None:
    """Verify ToolChoiceEvaluator checks selection of expected tool."""
    evaluator = ToolChoiceEvaluator(expected_tool="inspect_ast")
    assert evaluator.evaluate_raw("inspect_ast") is True
    assert evaluator.evaluate_raw("The best tool is inspect_ast.") is True
    assert evaluator.evaluate_raw("read_file") is False


def test_deep_recall_evaluator() -> None:
    """Verify DeepRecallEvaluator detects canary needle."""
    evaluator = DeepRecallEvaluator(canary="CANARY-RECALL-9824")
    assert evaluator.evaluate_raw("The code is CANARY-RECALL-9824.") is True
    assert evaluator.evaluate_raw("No canary here") is False


def test_explicit_prohibition_evaluator() -> None:
    """Verify ExplicitProhibitionEvaluator checks prefix and forbidden words."""
    evaluator = ExplicitProhibitionEvaluator(
        forbidden=("security", "vulnerability"),
        required_prefix="SUMMARY:",
    )
    assert evaluator.evaluate_raw("SUMMARY: Automated code review improves code quality.") is True
    # Missing prefix
    assert evaluator.evaluate_raw("Automated code review improves code quality.") is False
    # Contains forbidden word 'security'
    assert evaluator.evaluate_raw("SUMMARY: Automated review improves software security.") is False


def test_score_deployment_probes_full_pass() -> None:
    """Verify score_deployment_probes evaluates all 4 probes across trials using pydantic_evals."""
    probe_replies = {
        "json_adherence": [
            '```json\n{"file": "a.py", "line": 10, "severity": "HIGH", "rule_id": "R1", "description": "d"}\n```',
            '{"file": "b.py", "line": 20, "severity": "LOW", "rule_id": "R2", "description": "d2"}',
        ],
        "tool_choice": [
            "inspect_ast",
            "You should call inspect_ast for this task",
        ],
        "deep_recall": [
            "CANARY-RECALL-9824",
            "The verification code is CANARY-RECALL-9824",
        ],
        "explicit_prohibition": [
            "SUMMARY: Automated review finds structural bugs and defects.",
            "SUMMARY: Code inspections highlight syntax mistakes and performance issues.",
        ],
    }

    capabilities = score_deployment_probes(probe_replies, repeat=2)
    assert capabilities.probed is True
    assert capabilities.trials == 2
    assert capabilities.all_passed is True
    assert capabilities.passed_probes_count == 4
    assert capabilities.total_probes_count == 4
    # The first json reply was markdown fenced, so fix_llm_response repaired it
    assert capabilities.probes["json_adherence"].repaired >= 1
    assert "4/4 passed" in capabilities.summary_label


def test_score_deployment_probes_unmeasured() -> None:
    """Verify unmeasured deployment returns probed=False and appropriate label."""
    capabilities = score_deployment_probes({}, repeat=1)
    assert capabilities.probed is False
    assert capabilities.summary_label == "unmeasured"


def test_build_capability_probes() -> None:
    """Verify build_capability_probes constructs all four probes."""
    probes = build_capability_probes(prompt_tokens=500, max_input_tokens=1000, trials=3)
    assert len(probes) == 4
    names = [p["name"] for p in probes]
    assert names == [
        "json_adherence",
        "tool_choice",
        "deep_recall",
        "explicit_prohibition",
    ]
    for p in probes:
        assert p["rounds"] == 3
        assert "prompt" in p
        assert len(p["prompt"]) > 0


def test_probe_gateway_liveliness_and_models(stub_web: StubWeb) -> None:
    """Verify probe_gateway_liveliness_and_models verifies healthy liveliness and model info."""
    stub_web.respond("GET", "http://192.0.2.10:4000/health/liveliness", 200, {"status": "ok"})
    stub_web.respond("GET", "http://192.0.2.10:4000/model/info", 200, {"models": []})

    probe_gateway_liveliness_and_models("http://192.0.2.10:4000", {}, 5.0)

    stub_web.respond("GET", "http://192.0.2.10:4000/health/liveliness", 503, "Unavailable")
    with pytest.raises(ValidationError, match="not live"):
        probe_gateway_liveliness_and_models("http://192.0.2.10:4000", {}, 5.0)

    stub_web.respond("GET", "http://192.0.2.10:4000/health/liveliness", 200, {"status": "ok"})
    stub_web.respond("GET", "http://192.0.2.10:4000/model/info", 403, "Forbidden")
    with pytest.raises(ValidationError, match="rejected model info query"):
        probe_gateway_liveliness_and_models("http://192.0.2.10:4000", {}, 5.0)


def _status(*routes: GatewayRoute, healthy: bool = True) -> GatewayStatus:
    return GatewayStatus(
        healthy=healthy,
        gateway_url="https://gateway.example.com",
        active_routes=list(routes),
    )


def _route(name: str, *, healthy: bool = True) -> GatewayRoute:
    return GatewayRoute(
        virtual_model=name,
        target_model="qwen3.8:27b",
        backend_type="ollama",
        backend_url="https://gateway.example.com",
        healthy=healthy,
    )


def test_tier_health_skips_a_virtual_model_whose_route_is_unhealthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tier that the gateway reports unhealthy is not chosen (#3060)."""
    router = GatewayRouter(
        config=AIConfig(gateway_url="https://gateway.example.com"),
        state_file=tmp_path / "state.json",
    )
    monkeypatch.setattr(
        router,
        "probe_gateway",
        lambda **_: _status(_route("devops-coder", healthy=False), _route("devops-reasoning")),
    )

    assert router.tier_health(["devops-coder", "devops-reasoning"]) == {
        "devops-coder": False,
        "devops-reasoning": True,
    }


def test_tier_health_counts_a_name_that_the_gateway_does_not_route_as_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An `ollama:` model or a hosted group is not the gateway's to report on (#3060)."""
    router = GatewayRouter(
        config=AIConfig(gateway_url="https://gateway.example.com"),
        state_file=tmp_path / "state.json",
    )
    monkeypatch.setattr(
        router, "probe_gateway", lambda **_: _status(_route("devops-coder"), healthy=True)
    )

    assert router.tier_health(["devops-coder", "ollama:qwen3.8:27b", "claude-haiku-5-5"]) == {
        "devops-coder": True,
        "ollama:qwen3.8:27b": True,
        "claude-haiku-5-5": True,
    }


def test_tier_health_reports_every_virtual_model_unhealthy_when_the_gateway_is_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    router = GatewayRouter(state_file=tmp_path / "state.json")

    def refuse(**_: object) -> GatewayStatus:
        raise ValidationError("the gateway is down")

    monkeypatch.setattr(router, "probe_gateway", refuse)

    assert router.tier_health(["devops-coder", "devops-reasoning"]) == {
        "devops-coder": False,
        "devops-reasoning": False,
    }


def test_tier_health_of_no_tier_returns_no_reading(tmp_path: Path) -> None:
    router = GatewayRouter(state_file=tmp_path / "state.json")

    assert router.tier_health([]) == {}
