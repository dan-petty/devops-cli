"""The reply of the model to intake: its schema, an invalid answer, and the model that the triage
task uses (#1335).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.config.settings import AIConfig
from devops_cli.roadmap.intake.intake import (
    Outcome,
    apply_intake,
    plan_intake,
    render_intake,
)
from devops_cli.roadmap.intake.intake_model import (
    GatewayIntakeModel,
    ModelProposal,
    ProposalRequest,
)
from tests.support.fakes.model import ModelFake
from tests.support.roadmap_intake import DEFAULT_PROPOSAL, REPO, Embedder, FakeModel, Roadmap


def test_a_proposal_with_a_value_off_its_list_is_skipped_and_writes_nothing(
    roadmap: Roadmap,
) -> None:
    number = roadmap.issue("feat: odd")
    plan = roadmap.plan(FakeModel(proposals={"feat: odd": {"value": "Enormous"}}))
    (decision,) = plan.decisions
    assert (decision.outcome, decision.subject.number, plan.has_writes) == (
        Outcome.SKIP,
        number,
        False,
    )


@dataclass
class _SchemaClient:
    """Answers each proposal request with `DEFAULT_PROPOSAL`, and records the reply schema."""

    schemas: list[type[ModelProposal]] = field(default_factory=list)

    def chat_structured(
        self, system: str, prompt: str, schema: type[ModelProposal]
    ) -> ModelProposal:
        self.schemas.append(schema)
        return schema.model_validate(DEFAULT_PROPOSAL)


def _reply_schema(types: tuple[str, ...]) -> type[ModelProposal]:
    """The reply schema that intake sends with a proposal request for `types`."""
    client = _SchemaClient()
    GatewayIntakeModel(AIConfig(), client=client).propose(
        ProposalRequest(title="t", body="b", shortlist=(), types=types)
    )
    return client.schemas[0]


def test_the_reply_schema_lists_the_values_of_each_fixed_field() -> None:
    """The model's structured output keeps to the schema's enums, so it cannot leave `type`
    empty or name a value off its list (#2370)."""
    schema = _reply_schema(("type/bug", "type/feature")).model_json_schema()

    fixed = ("type", "priority", "value", "effort")
    assert (
        {name: schema["properties"][name].get("enum") for name in fixed},
        set(fixed) <= set(schema["required"]),
    ) == (
        {
            "type": ["type/bug", "type/feature"],
            "priority": ["P1-High", "P2-Medium", "P3-Low"],
            "value": ["High", "Medium", "Low"],
            "effort": ["High", "Medium", "Low"],
        },
        True,
    )


def test_the_reply_schema_refuses_an_empty_type() -> None:
    schema = _reply_schema(("type/bug", "type/feature"))

    with pytest.raises(ValidationError) as caught:
        schema.model_validate({**DEFAULT_PROPOSAL, "type": ""})

    assert [error["loc"] for error in caught.value.errors()] == [("type",)]


def test_a_request_with_no_types_keeps_type_as_free_text() -> None:
    schema = _reply_schema(()).model_json_schema()

    assert schema["properties"]["type"] == {"default": "", "title": "Type", "type": "string"}


def test_a_model_answer_that_fails_validation_skips_only_its_candidate(roadmap: Roadmap) -> None:
    """A model that answers, but not in the schema, is not an unreachable gateway: that one
    candidate is skipped with the reason, and the others are placed."""

    class Client:
        def chat_structured(
            self, system: str, prompt: str, schema: type[ModelProposal]
        ) -> ModelProposal:
            if "feat: garbled" in prompt:
                raise StructuredOutputValidationError("Response validation failed after 3 tries")
            return schema.model_validate(DEFAULT_PROPOSAL)

    model = GatewayIntakeModel(AIConfig(), embedder=Embedder(), client=Client())
    garbled = roadmap.issue("feat: garbled")
    fine = roadmap.issue("feat: fine")
    plan = plan_intake(roadmap.store, repo=REPO, model=model)
    apply_intake(roadmap.store, plan, repo=REPO)
    skipped = plan.decisions[0]
    assert (
        [d.outcome for d in plan.decisions],
        "Response validation failed" in skipped.reason,
        roadmap.store.item(garbled),
        roadmap.fields(fine)[1],
    ) == ([Outcome.SKIP, Outcome.PLACE], True, None, "P2-Medium")


def test_an_off_list_proposal_skips_its_candidate_after_one_model_call(roadmap: Roadmap) -> None:
    """The reply schema keeps the gateway model's values on their lists (#2370), and
    `chat_structured` asks again when a reply breaks it, so intake asks once: a proposal that
    still names a value off its list skips the candidate with the problem in the report."""
    issue = roadmap.issue("A bad type")
    model = FakeModel(proposals={"A bad type": {"type": "type/perf"}})

    plan = roadmap.plan(model)
    apply_intake(roadmap.store, plan, repo=REPO)

    (decision,) = plan.decisions
    assert (
        decision.outcome,
        len(model.requests),
        "type 'type/perf' is not one of" in decision.reason,
        "type 'type/perf' is not one of" in render_intake(plan, repo=REPO),
        roadmap.store.item(issue),
    ) == (Outcome.SKIP, 1, True, True, None)


def test_intake_proposal_uses_triage_task_model_or_falls_back_to_ai_model(
    model_fake: ModelFake,
) -> None:
    """Intake uses ai.tasks.triage model when set; when unset, it falls back to ai.model."""
    from devops_cli.config.settings import AIConfig, AITaskOverride, AITasksConfig
    from devops_cli.roadmap.intake.intake_model import GatewayIntakeModel

    request = ProposalRequest(title="t", body="b", shortlist=(), types=("type/feature",))
    model_fake.answer(json.dumps(DEFAULT_PROPOSAL))

    # 1. Unset triage task: falls back to ai.model
    ai_unset = AIConfig(model="base-chat-model")
    GatewayIntakeModel(ai_unset, embedder=Embedder()).propose(request)
    # 2. Set triage task: uses triage.model
    ai_set = AIConfig(
        model="base-chat-model",
        tasks=AITasksConfig(triage=AITaskOverride(model="devops-triage")),
    )
    GatewayIntakeModel(ai_set, embedder=Embedder()).propose(request)

    assert [(call["task"], call["config"].model) for call in model_fake.factory_calls] == [
        ("triage", "base-chat-model"),
        ("triage", "devops-triage"),
    ]
