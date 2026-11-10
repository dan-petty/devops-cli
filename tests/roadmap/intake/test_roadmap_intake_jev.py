"""Jev decides the proposal fields of intake (#4298): one System One request gives the type, the
priority, the Value, the Effort and the duplicate flags of a candidate, and any failure of Jev
leaves the call to the triage model."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
import pytest

from devops_cli.config.constants import CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD
from devops_cli.config.settings import load_settings
from devops_cli.roadmap.intake.intake import Outcome
from devops_cli.roadmap.intake.intake_jev import JevIntakeModel
from devops_cli.roadmap.intake.intake_model import (
    GatewayIntakeModel,
    ModelProposal,
    ProposalRequest,
    UnusableProposalError,
    build_intake_model,
)
from tests.support.roadmap_intake import FakeModel, Roadmap

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from tests.support.fakes.jev import JevFake
    from tests.support.fakes.otlp import FakeCollector

FIELDS_TOTAL = "devops_cli_roadmap_intake_jev_fields_total"
# Level 2 of the three levels is High; level 0 is Low.
HIGH, LOW = 2, 0


def _model(jev: JevFake, base: FakeModel | None = None) -> JevIntakeModel:
    return JevIntakeModel(base or FakeModel(topics=("embeddings",)), jev.model)


def _counts(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    """The sum of the counter for each (field, outcome) that has a point, after a check that a
    point holds the labels `field` and `outcome` and no other."""
    found: dict[tuple[str, str], float] = {}
    for attrs, value in otlp.points(FIELDS_TOTAL):
        assert set(attrs) == {"field", "outcome"}
        key = (attrs["field"], attrs["outcome"])
        found[key] = found.get(key, 0.0) + value
    return found


def test_jev_gives_the_fields_of_a_proposal_and_the_triage_model_is_not_asked(
    roadmap: Roadmap, jev: JevFake
) -> None:
    jev.picks = {"type": "type/bug", "priority": "P1-High", "value": HIGH, "effort": LOW}
    roadmap.issue("Cache embeddings")
    base = FakeModel()

    (decision,) = roadmap.plan(_model(jev, base)).decisions

    assert (decision.outcome, decision.shown, base.requests) == (
        Outcome.PLACE,
        ("type/bug", "P1-High", "High", "Low"),
        [],
    )
    assert jev.asked == [["type", "priority", "value", "effort"]]


def test_jev_is_not_asked_for_a_type_when_the_title_gives_one(
    roadmap: Roadmap, jev: JevFake
) -> None:
    roadmap.issue("fix(ci): the cache key ignores the lock file")

    roadmap.plan(_model(jev))

    assert jev.asked == [["priority", "value", "effort"]]


def test_jev_asks_one_noul_question_for_each_nearest_item(roadmap: Roadmap, jev: JevFake) -> None:
    first = roadmap.issue("Cache embeddings")
    roadmap.issue("Keep embeddings cached")

    roadmap.plan(_model(jev))

    assert jev.asked[-1] == [
        "type",
        "priority",
        "value",
        "effort",
        f"duplicate_of_{first}",
    ]


def test_a_neighbour_that_jev_is_sure_of_is_flagged_and_the_candidate_is_still_placed(
    roadmap: Roadmap, jev: JevFake
) -> None:
    first = roadmap.issue("Cache embeddings")
    second = roadmap.issue("Keep embeddings cached")
    jev.picks = {f"duplicate_of_{first}": CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD}

    first_decision, second_decision = roadmap.plan(_model(jev)).decisions

    assert (
        first_decision.possible_duplicate,
        second_decision.possible_duplicate,
        second_decision.outcome,
        roadmap.store.closures(second),
    ) == (None, first, Outcome.PLACE, [])


def test_a_neighbour_below_the_threshold_is_not_flagged(roadmap: Roadmap, jev: JevFake) -> None:
    first = roadmap.issue("Cache embeddings")
    roadmap.issue("Keep embeddings cached")
    jev.picks = {f"duplicate_of_{first}": CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD - 0.05}

    decisions = roadmap.plan(_model(jev)).decisions

    assert [decision.possible_duplicate for decision in decisions] == [None, None]


def test_a_reply_of_jev_that_fails_leaves_the_proposal_to_the_triage_model(
    roadmap: Roadmap, jev: JevFake
) -> None:
    jev.fail(503)
    roadmap.issue("Cache embeddings")
    base = FakeModel(proposals={"Cache embeddings": {"priority": "P3-Low", "value": "Low"}})

    (decision,) = roadmap.plan(_model(jev, base)).decisions

    assert (decision.outcome, decision.shown, len(base.requests)) == (
        Outcome.PLACE,
        ("type/feature", "P3-Low", "Low", "Low"),
        1,
    )


def test_a_gateway_that_cannot_be_reached_leaves_the_proposal_to_the_triage_model(
    roadmap: Roadmap, jev: JevFake
) -> None:
    jev.unreachable(httpx2.ConnectError("no route"))
    roadmap.issue("Cache embeddings")
    base = FakeModel()

    roadmap.plan(_model(jev, base))

    assert len(base.requests) == 1


def test_a_low_confidence_leaves_the_proposal_to_the_triage_model(
    roadmap: Roadmap, jev: JevFake
) -> None:
    jev.confidence = 0.4
    roadmap.issue("Cache embeddings")
    base = FakeModel()

    roadmap.plan(_model(jev, base))

    assert len(base.requests) == 1


def test_an_evaluation_model_without_a_fallback_skips_the_candidate_that_jev_cannot_decide(
    roadmap: Roadmap, jev: JevFake
) -> None:
    jev.fail(503)
    roadmap.issue("Cache embeddings")
    model = JevIntakeModel(FakeModel(), jev.model, fall_back=False)

    (decision,) = roadmap.plan(model).decisions

    assert decision.outcome is Outcome.SKIP


def test_a_request_that_jev_cannot_decide_without_a_fallback_raises_unusable_proposal(
    jev: JevFake,
) -> None:
    jev.fail(503)
    model = JevIntakeModel(FakeModel(), jev.model, fall_back=False)
    request = ProposalRequest(title="Cache embeddings", body="", shortlist=(), types=("type/bug",))

    with pytest.raises(UnusableProposalError) as raised:
        model.propose(request)

    assert "503" in str(raised.value)


def test_the_counter_holds_one_series_for_each_field_and_outcome(
    roadmap: Roadmap, jev: JevFake, otlp: FakeCollector
) -> None:
    roadmap.issue("Cache embeddings")
    roadmap.issue("Keep embeddings cached")
    roadmap.plan(_model(jev))
    jev.fail(503)
    roadmap.issue("Another idea")
    roadmap.plan(_model(jev))

    counts = _counts(otlp)

    assert {outcome for _, outcome in counts} == {"jev", "fallback"}
    assert {field for field, _ in counts} <= {"type", "priority", "value", "effort", "duplicate"}
    assert counts[("priority", "jev")] > 0
    assert counts[("priority", "fallback")] > 0


def test_a_candidate_with_no_neighbour_asks_no_duplicate_question_and_counts_none(
    roadmap: Roadmap, jev: JevFake, otlp: FakeCollector
) -> None:
    roadmap.issue("Cache embeddings")

    roadmap.plan(_model(jev, FakeModel()))

    assert ("duplicate", "jev") not in _counts(otlp)


def test_the_setting_off_builds_the_triage_model_and_on_builds_jev(
    config: Callable[..., Any], keyring_store: Any
) -> None:
    config()
    off = build_intake_model()
    config(roadmap={"intake": {"jev": True}})
    on = build_intake_model()

    assert (type(off), type(on)) == (GatewayIntakeModel, JevIntakeModel)


def test_the_reply_of_jev_has_the_shape_of_the_triage_reply(jev: JevFake) -> None:
    jev.picks = {"type": "type/bug", "priority": "P2-Medium", "value": 1, "effort": 1}
    request = ProposalRequest(
        title="Cache embeddings",
        body="The embedder runs twice.",
        shortlist=(),
        types=("type/bug", "type/feature"),
    )

    proposal = _model(jev).propose(request)

    assert isinstance(proposal, ModelProposal)
    assert (proposal.type, proposal.priority, proposal.value, proposal.effort) == (
        "type/bug",
        "P2-Medium",
        "Medium",
        "Medium",
    )


def test_a_model_that_owns_its_http_client_decides_one_request_after_another(
    jev: JevFake,
) -> None:
    """Each request runs on its own event loop, and the connection of the first request must not
    be reused on the second."""
    model = JevIntakeModel(FakeModel(), jev.over_loopback(), fall_back=False)
    request = ProposalRequest(
        title="Cache embeddings", body="", shortlist=(), types=("type/bug", "type/feature")
    )

    first, second = model.propose(request), model.propose(request)

    assert (first.priority, second.priority, len(jev.requests)) == ("P1-High", "P1-High", 2)


def test_a_model_the_gateway_settings_build_decides_one_request_after_another(
    jev: JevFake, config: Callable[..., Any], keyring_store: Any
) -> None:
    """The client of such a model is not the provider's own, so the model closes it on the loop
    that used it, and the next request opens a new one."""
    jev.over_loopback()
    config(ai={"provider": "gateway", "gateway_url": jev.url, "allow_private_network": True})
    model = JevIntakeModel(FakeModel(), settings=load_settings(), fall_back=False)
    request = ProposalRequest(
        title="Cache embeddings", body="", shortlist=(), types=("type/bug", "type/feature")
    )

    first, second = model.propose(request), model.propose(request)

    assert (first.priority, second.priority, len(jev.requests)) == ("P1-High", "P1-High", 2)


def test_the_least_confidence_is_a_parameter_of_the_model(jev: JevFake) -> None:
    jev.confidence = 0.4
    request = ProposalRequest(title="Cache embeddings", body="", shortlist=(), types=("type/bug",))

    proposal = JevIntakeModel(FakeModel(), jev.model, fall_back=False, min_confidence=0.3).propose(
        request
    )

    assert proposal.priority == "P1-High"
