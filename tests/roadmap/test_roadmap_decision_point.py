"""Decision points (ADR 0020): the resolver chain of a point, its records and its one counter, the
join of a decision with its outcome, and the registry of the points."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.models.decision import NoulQuestion

from devops_cli.config.constants import (
    CONST_AI_JEV_MODEL,
    CONST_ROADMAP_DECISION_POINT_MAX_SERIES,
)
from devops_cli.roadmap.decision_fit import FitCase
from devops_cli.roadmap.decision_point import (
    DecisionPoint,
    DecisionRecord,
    Mode,
    OutcomeRecord,
    Registry,
    Resolver,
    ResolverChain,
    join,
    parse_record,
    record_outcome,
)
from devops_cli.roadmap.decision_registry import REGISTRY
from devops_cli.roadmap.decision_step import Band
from devops_cli.telemetry.instruments import DECISION_POINT_TOTAL, INSTRUMENTS

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from tests.support.fakes.jev import JevFake
    from tests.support.fakes.otlp import FakeCollector

COUNTER = "devops_cli_decision_point_total"
FAILED_COUNTER = "devops_cli_decision_point_failed_total"
BANDS = {Band.CONTINUE: "skip the costly path", Band.REVIEW: "run it", Band.FLAG: "run it, log"}
SECRET = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"

type Rule = Callable[[Mapping[str, Any]], Band | None]


def _cuts(directory: Path, names: tuple[str, ...] = ("a", "b")) -> Path:
    path = directory / "cuts.json"
    path.write_text(
        json.dumps(
            {
                "step": "demo.point",
                "model": CONST_AI_JEV_MODEL,
                "fitted": "2026-11-10",
                "cases": 40,
                "cuts": {name: {"continue_below": 0.3, "flag_at": 0.8} for name in names},
                "report": {"other_half": {"skip_rate": 0.1}},
            }
        ),
        encoding="utf-8",
    )
    return path


def _point(
    cuts: Path,
    *,
    name: str = "demo.point",
    rule: Rule | None = None,
    asks_model: bool = True,
    counts_only: bool = False,
    timeout: float = 30.0,
) -> DecisionPoint[dict[str, Any]]:
    return DecisionPoint(
        name=name,
        questions={
            "a": NoulQuestion(instructions="Does the case need the costly path for a?"),
            "b": NoulQuestion(instructions="Does the case need the costly path for b?"),
        },
        evidence=dict,
        bands=BANDS,
        cuts=cuts,
        rule=rule,
        asks_model=asks_model,
        counts_only=counts_only,
        timeout=timeout,
    )


def _chain(
    point: DecisionPoint[dict[str, Any]], jev: JevFake, mode: Mode = Mode.ON
) -> ResolverChain[dict[str, Any]]:
    return ResolverChain(point, mode, model_name=CONST_AI_JEV_MODEL, model=jev.model)


def _records(caplog: pytest.LogCaptureFixture) -> list[DecisionRecord | OutcomeRecord]:
    found = [parse_record(record.getMessage()) for record in caplog.records]
    return [record for record in found if record is not None]


def test_a_proven_rule_answers_first_and_no_request_goes_to_the_model(
    tmp_path: Path, jev: JevFake, otlp: FakeCollector
) -> None:
    point = _point(_cuts(tmp_path), rule=lambda digest: Band.CONTINUE)

    decision = _chain(point, jev).decide({"edits": 1}, subject=7)

    assert (decision.resolver, decision.band, decision.acts) == (Resolver.RULE, Band.CONTINUE, True)
    assert jev.requests == []
    assert otlp.points(COUNTER) == [
        ({"point": "demo.point", "resolver": "rule", "band": "continue", "mode": "on"}, 1)
    ]


def test_a_rule_with_no_band_leaves_the_case_to_the_model(tmp_path: Path, jev: JevFake) -> None:
    jev.picks = {"a": 0.5}
    point = _point(_cuts(tmp_path), rule=lambda digest: None)

    decision = _chain(point, jev).decide({"edits": 0}, subject=7)

    assert (decision.resolver, decision.band) == (Resolver.MODEL, Band.REVIEW)
    assert jev.asked == [["a", "b"]]


def test_decide_and_adecide_answer_inside_a_running_event_loop(
    tmp_path: Path, jev: JevFake
) -> None:
    """A caller that runs an event loop gets the decision of the model from either entry point:
    `decide` sends on the portal of the process, and `adecide` awaits the same request on the loop
    of the caller (#5272). Each path builds its own model, because the pooled client of a model
    belongs to one loop (#4319)."""
    point = _point(_cuts(tmp_path))

    async def drive() -> tuple[DecisionRecord, DecisionRecord]:
        blocked = _chain(point, jev).decide({"text": "a plan"}, subject=7)
        awaited = await ResolverChain(
            point, Mode.ON, model_name=CONST_AI_JEV_MODEL, model=jev.over_loopback()
        ).adecide({"text": "a plan"}, subject=7)
        return blocked, awaited

    blocked, awaited = asyncio.run(drive())

    for decision in (blocked, awaited):
        assert (decision.resolver, decision.band, decision.cuts) == (
            Resolver.MODEL,
            Band.CONTINUE,
            "2026-11-10",
        )


@pytest.mark.parametrize(
    ("picks", "band", "flagged"),
    [
        ({}, Band.CONTINUE, []),
        ({"a": 0.3}, Band.REVIEW, []),
        ({"b": 0.8}, Band.FLAG, ["b"]),
    ],
)
def test_the_model_answers_all_questions_in_one_request_and_the_cuts_give_the_band(
    tmp_path: Path,
    jev: JevFake,
    caplog: pytest.LogCaptureFixture,
    picks: dict[str, float],
    band: Band,
    flagged: list[str],
) -> None:
    jev.picks = dict(picks)

    with caplog.at_level(logging.INFO):
        decision = _chain(_point(_cuts(tmp_path)), jev).decide({"text": "a plan"}, subject=7)

    assert (decision.resolver, decision.band, decision.acts) == (Resolver.MODEL, band, True)
    assert jev.asked == [["a", "b"]]
    assert _records(caplog) == [decision]
    assert (decision.model, decision.cuts, decision.flagged) == (
        CONST_AI_JEV_MODEL,
        "2026-11-10",
        flagged,
    )


def test_shadow_records_the_band_and_the_decision_does_not_act(
    tmp_path: Path, jev: JevFake, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        decision = _chain(_point(_cuts(tmp_path)), jev, Mode.SHADOW).decide(
            {"text": "a plan that names src/job.py"}, subject=7
        )

    assert (decision.mode, decision.band, decision.acts) == (Mode.SHADOW, Band.CONTINUE, False)
    assert otlp.points(COUNTER) == [
        ({"point": "demo.point", "resolver": "model", "band": "continue", "mode": "shadow"}, 1)
    ]
    assert decision.answers == {"a": 0.02, "b": 0.02}
    assert decision.digest is None
    assert len(decision.digest_sha256) == 64
    assert "src/job.py" not in caplog.text


def test_a_digest_of_counts_is_in_the_record(tmp_path: Path, jev: JevFake) -> None:
    point = _point(_cuts(tmp_path), counts_only=True)

    decision = _chain(point, jev, Mode.SHADOW).decide({"calls": 30, "files": 4}, subject="run-1")

    assert decision.digest == {"calls": 30, "files": 4}


def test_a_model_error_falls_back_and_names_the_error(
    tmp_path: Path, jev: JevFake, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    jev.fail(503)

    with caplog.at_level(logging.WARNING):
        decision = _chain(_point(_cuts(tmp_path)), jev).decide({"text": "a plan"}, subject=7)

    assert (decision.resolver, decision.band, decision.acts) == (Resolver.FALLBACK, None, False)
    assert "current behavior runs" in caplog.text
    assert "503" in caplog.text
    assert otlp.points(COUNTER) == [
        ({"point": "demo.point", "resolver": "fallback", "band": "none", "mode": "on"}, 1)
    ]


def test_a_failed_request_gives_the_fallback_and_counts_its_class(
    tmp_path: Path, jev: JevFake, otlp: FakeCollector
) -> None:
    """A model that raises an error no class of `FAILED` names gives the fallback, and the failed
    counter holds the class `other`. A request that the timeout ends counts the class `timeout`
    (#5272)."""
    jev.unreachable(RuntimeError("the decision model broke"))

    broken = _chain(_point(_cuts(tmp_path)), jev).decide({"text": "a plan"}, subject=7)

    assert (broken.resolver, broken.band) == (Resolver.FALLBACK, None)
    assert otlp.points(FAILED_COUNTER) == [({"point": "demo.point", "error": "other"}, 1)]

    otlp.clear()
    jev.error = None
    jev.hold()
    slow = _chain(_point(_cuts(tmp_path), timeout=0.01), jev).decide({"text": "a plan"}, subject=7)

    assert (slow.resolver, slow.band) == (Resolver.FALLBACK, None)
    assert otlp.points(FAILED_COUNTER) == [({"point": "demo.point", "error": "timeout"}, 1)]


def test_the_failure_classes_are_seven() -> None:
    from devops_cli.roadmap.decision_step import FailureClass

    assert {klass.value for klass in FailureClass} == {
        "timeout",
        "model_error",
        "parse",
        "secret",
        "no_cuts",
        "model_mismatch",
        "other",
    }


def test_a_question_with_no_answer_falls_back_and_keeps_the_answers(
    tmp_path: Path, jev: JevFake
) -> None:
    point = _point(_cuts(tmp_path, ("a", "b", "c")))

    decision = _chain(point, jev).decide({"text": "a plan"}, subject=7)

    assert (decision.resolver, decision.band) == (Resolver.FALLBACK, None)
    assert decision.answers == {"a": 0.02, "b": 0.02}


def test_a_digest_with_a_secret_sends_no_request_and_falls_back(
    tmp_path: Path, jev: JevFake, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        decision = _chain(_point(_cuts(tmp_path)), jev).decide({"text": SECRET}, subject=7)

    assert (decision.resolver, jev.requests) == (Resolver.FALLBACK, [])
    assert "holds a secret" in caplog.text
    assert SECRET not in caplog.text


def test_each_decision_has_its_own_identifier_of_the_point_and_the_subject(
    tmp_path: Path, jev: JevFake
) -> None:
    chain = _chain(_point(_cuts(tmp_path)), jev)

    first = chain.decide({"text": "a plan"}, subject=7)
    second = chain.decide({"text": "a plan"}, subject=7)

    assert first.id != second.id
    assert first.id.startswith("demo.point/7/")
    assert (first.point, first.subject) == ("demo.point", "7")


def test_a_chain_with_no_resolver_or_in_mode_off_is_refused(tmp_path: Path, jev: JevFake) -> None:
    with pytest.raises(ValueError, match="no resolver"):
        ResolverChain(_point(_cuts(tmp_path)), Mode.ON, model_name="")
    with pytest.raises(ValueError, match="off"):
        _chain(_point(_cuts(tmp_path)), jev, Mode.OFF)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"name": "verify_screen"}, "<area>.<what>"),
        ({"bands": {Band.CONTINUE: "skip"}}, "band"),
        ({"asks_model": False}, "no resolver"),
    ],
)
def test_a_point_must_have_a_name_three_bands_and_a_resolver(
    tmp_path: Path, changes: dict[str, Any], match: str
) -> None:
    values: dict[str, Any] = {
        "name": "demo.point",
        "questions": {"a": NoulQuestion(instructions="a?")},
        "evidence": dict,
        "bands": BANDS,
        "cuts": tmp_path / "cuts.json",
        **changes,
    }

    with pytest.raises(ValueError, match=match):
        DecisionPoint(**values)


def test_a_point_writes_only_its_label_sets(
    tmp_path: Path, jev: JevFake, otlp: FakeCollector
) -> None:
    point = _point(_cuts(tmp_path))
    for mode in (Mode.SHADOW, Mode.ON):
        for pick in (0.0, 0.3, 0.8):
            jev.picks = {"a": pick}
            _chain(point, jev, mode).decide({"text": "a plan"}, subject=1)
    jev.fail(503)
    for mode in (Mode.SHADOW, Mode.ON):
        _chain(point, jev, mode).decide({"text": "a plan"}, subject=1)

    written = {
        (labels["point"], labels["resolver"], labels["band"], labels["mode"])
        for labels, _ in otlp.points(COUNTER)
    }

    assert written == point.series()
    assert len(point.series()) == 8
    assert len(_point(_cuts(tmp_path), rule=lambda digest: None).series()) == 14


def test_the_registry_refuses_a_catalogue_above_60_series(tmp_path: Path) -> None:
    points = [_point(_cuts(tmp_path), name=f"demo.point_{index}") for index in range(8)]

    with pytest.raises(ValueError, match="60"):
        Registry(points)


def test_the_registry_gives_the_fitted_cuts_of_a_point(tmp_path: Path) -> None:
    registry = Registry([_point(_cuts(tmp_path))])

    fitted = registry.point("demo.point").thresholds()
    assert (fitted.step, fitted.fitted, sorted(fitted.cuts)) == (
        "demo.point",
        "2026-11-10",
        ["a", "b"],
    )


def test_the_join_labels_each_decision_that_has_an_outcome(
    tmp_path: Path, jev: JevFake, caplog: pytest.LogCaptureFixture
) -> None:
    chain = _chain(_point(_cuts(tmp_path)), jev, Mode.SHADOW)
    with caplog.at_level(logging.INFO):
        decisions = [chain.decide({"text": "a plan"}, subject=item) for item in (1, 2, 3)]
        found = record_outcome(decisions[0], must_run=True, weight=2, result="found")
        clean = record_outcome(decisions[2], must_run=False, weight=0, result="clean")
    records = _records(caplog)

    joined = join(
        [r for r in records if isinstance(r, DecisionRecord)],
        [r for r in records if isinstance(r, OutcomeRecord)],
    )

    assert [(case.decision, case.outcome) for case in joined.cases] == [
        (decisions[0], found),
        (decisions[2], clean),
    ]
    assert joined.unmatched == (decisions[1],)
    assert joined.fit_cases() == [
        FitCase(decisions[0].id, {"a": 0.02, "b": 0.02}, must_run=True, weight=2),
        FitCase(decisions[2].id, {"a": 0.02, "b": 0.02}, must_run=False, weight=0),
    ]


def test_a_line_that_is_no_record_reads_as_none() -> None:
    assert parse_record("The stage job planned item #7.") is None
    assert parse_record("decision {not json") is None


def test_one_counter_counts_the_decisions_and_states_the_bound_of_the_catalogue() -> None:
    names = {instrument.name for instrument in INSTRUMENTS}

    assert COUNTER in names
    assert (
        not {
            "devops_cli_roadmap_decision_step_total",
            "devops_cli_roadmap_decision_step_review_total",
        }
        & names
    )
    assert "60 series" in DECISION_POINT_TOTAL.description
    assert REGISTRY.series_count <= CONST_ROADMAP_DECISION_POINT_MAX_SERIES == 60
