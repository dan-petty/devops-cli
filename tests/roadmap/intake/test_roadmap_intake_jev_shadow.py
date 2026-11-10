"""The shadow mode of the Jev intake labels (#4395): the triage model decides every label and
flag, Jev answers beside it, and intake records the pair in the job record of the issue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx2
import pytest
from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD
from devops_cli.config.settings import RoadmapIntakeConfig, Settings
from devops_cli.roadmap.intake.intake import Outcome
from devops_cli.roadmap.intake.intake_jev import JevIntakeModel
from devops_cli.roadmap.intake.intake_jev_shadow import ShadowIntakeModel, ShadowObservation
from devops_cli.roadmap.intake.intake_model import GatewayIntakeModel, build_intake_model
from devops_cli.roadmap.intake.intake_requests import SpendMeter
from devops_cli.roadmap.stores.store import IntakeRecordKey
from tests.support.roadmap_intake import FakeModel, Roadmap

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from tests.support.fakes.jev import JevFake
    from tests.support.fakes.otlp import FakeCollector

SHADOW_TOTAL = "devops_cli_roadmap_intake_jev_shadow_total"
FIELDS_TOTAL = "devops_cli_roadmap_intake_jev_fields_total"
AT = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
# Level 2 of the three levels is High; level 0 is Low.
HIGH, LOW = 2, 0


def _model(jev: JevFake, base: FakeModel | None = None) -> ShadowIntakeModel:
    return ShadowIntakeModel(base or FakeModel(topics=("embeddings",)), jev.model, now=lambda: AT)


def _counts(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    found: dict[tuple[str, str], float] = {}
    for attrs, value in otlp.points(SHADOW_TOTAL):
        assert set(attrs) == {"field", "outcome"}
        key = (attrs["field"], attrs["outcome"])
        found[key] = found.get(key, 0.0) + value
    return found


def _marks(roadmap: Roadmap, number: int) -> str | None:
    issue = next(each for each in roadmap.store.issues() if each.number == number)
    return issue.job_record.get(IntakeRecordKey.JEV_SHADOW)


def test_shadow_changes_no_label_and_no_flag_of_the_proposal(
    roadmap: Roadmap, jev: JevFake
) -> None:
    """Jev answers differently from the triage model on every field, and the proposal is the
    triage model's alone."""
    jev.picks = {"type": "type/bug", "priority": "P1-High", "value": HIGH, "effort": HIGH}
    first = roadmap.issue("Cache embeddings")
    roadmap.issue("Keep embeddings cached")
    jev.picks[f"duplicate_of_{first}"] = CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD
    triage = FakeModel(topics=("embeddings",))
    plain = FakeModel(topics=("embeddings",))

    shadowed = roadmap.plan(_model(jev, triage)).decisions
    expected = roadmap.plan(plain).decisions

    assert [(d.outcome, d.shown, d.possible_duplicate) for d in shadowed] == [
        (d.outcome, d.shown, d.possible_duplicate) for d in expected
    ]
    assert all(d.outcome is Outcome.PLACE for d in shadowed)
    assert shadowed[1].shown == ("type/feature", "P2-Medium", "Medium", "Low")


def test_a_placement_records_the_answers_of_jev_beside_those_of_the_triage_model(
    roadmap: Roadmap, jev: JevFake
) -> None:
    jev.picks = {"type": "type/bug", "priority": "P1-High", "value": HIGH, "effort": LOW}
    number = roadmap.issue("Cache embeddings")

    roadmap.run(_model(jev))

    mark = _marks(roadmap, number)
    assert mark is not None
    observation = ShadowObservation.from_mark(mark)
    assert observation.at == AT
    assert {name: tuple(answer) for name, answer in observation.answers.items()} == {
        "type": ("type/bug", 0.9, "type/feature"),
        "priority": ("P1-High", 0.9, "P2-Medium"),
        "value": ("High", 0.9, "Medium"),
        "effort": ("Low", 0.9, "Low"),
    }


def test_the_mark_holds_no_text_of_the_issue(roadmap: Roadmap, jev: JevFake) -> None:
    number = roadmap.issue("Cache embeddings", body="The embedder runs twice for one text.")

    roadmap.run(_model(jev))

    mark = _marks(roadmap, number) or ""
    assert "embedder" not in mark
    assert "Cache" not in mark
    assert len(mark) < 400


def test_the_duplicate_field_records_the_flag_and_the_probability_and_closes_nothing(
    roadmap: Roadmap, jev: JevFake
) -> None:
    first = roadmap.issue("Cache embeddings")
    second = roadmap.issue("Keep embeddings cached")
    jev.picks = {f"duplicate_of_{first}": CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD}
    triage = FakeModel(
        topics=("embeddings",), duplicates={"Keep embeddings cached": "Cache embeddings"}
    )

    roadmap.run(_model(jev, triage))

    mark = _marks(roadmap, second)
    assert mark is not None
    answer = ShadowObservation.from_mark(mark).answers["duplicate"]
    assert tuple(answer) == (str(first), CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD, str(first))
    assert roadmap.store.closures(second) == []
    assert roadmap.fields(second)[1] is not None


def test_a_neighbour_below_the_threshold_is_recorded_with_no_flag(
    roadmap: Roadmap, jev: JevFake
) -> None:
    first = roadmap.issue("Cache embeddings")
    second = roadmap.issue("Keep embeddings cached")
    jev.picks = {f"duplicate_of_{first}": 0.4}

    roadmap.run(_model(jev))

    answer = ShadowObservation.from_mark(_marks(roadmap, second) or "").answers["duplicate"]
    assert tuple(answer) == ("", 0.4, "")


def test_a_candidate_whose_title_gives_the_type_has_no_type_answer(
    roadmap: Roadmap, jev: JevFake
) -> None:
    number = roadmap.issue("fix(ci): the cache key ignores the lock file")

    roadmap.run(_model(jev))

    answers = ShadowObservation.from_mark(_marks(roadmap, number) or "").answers
    assert set(answers) == {"priority", "value", "effort"}


def test_a_jev_error_changes_nothing_records_nothing_and_counts_jev_error(
    roadmap: Roadmap, jev: JevFake, otlp: FakeCollector
) -> None:
    jev.fail(503)
    number = roadmap.issue("Cache embeddings")
    plain = Roadmap()
    expected = plain.issue("Cache embeddings")
    plain.run(FakeModel(topics=("embeddings",)))

    roadmap.run(_model(jev))

    assert _marks(roadmap, number) is None
    assert roadmap.fields(number) == plain.fields(expected)
    counts = _counts(otlp)
    assert set(counts) == {
        ("type", "jev_error"),
        ("priority", "jev_error"),
        ("value", "jev_error"),
        ("effort", "jev_error"),
    }


def test_an_unreachable_gateway_changes_nothing(roadmap: Roadmap, jev: JevFake) -> None:
    jev.unreachable(httpx2.ConnectError("no route"))
    number = roadmap.issue("Cache embeddings")

    decisions = roadmap.plan(_model(jev)).decisions

    assert [d.outcome for d in decisions] == [Outcome.PLACE]
    assert _marks(roadmap, number) is None


def test_a_low_confidence_is_recorded_and_not_used(roadmap: Roadmap, jev: JevFake) -> None:
    jev.confidence = 0.3
    number = roadmap.issue("Cache embeddings")

    (decision,) = roadmap.plan(_model(jev)).decisions
    roadmap.run(_model(jev))

    answers = ShadowObservation.from_mark(_marks(roadmap, number) or "").answers
    assert answers["priority"].probability == 0.3
    assert decision.shown == ("type/feature", "P2-Medium", "Medium", "Low")


def test_agreement_counts_agree_and_differ_for_each_field(
    roadmap: Roadmap, jev: JevFake, otlp: FakeCollector
) -> None:
    """The triage model says feature, P2, Medium, Low. Jev agrees on the priority and the
    effort only."""
    jev.picks = {"type": "type/bug", "priority": "P2-Medium", "value": HIGH, "effort": LOW}
    roadmap.issue("Cache embeddings")

    roadmap.plan(_model(jev))

    assert _counts(otlp) == {
        ("type", "differ"): 1,
        ("priority", "agree"): 1,
        ("value", "differ"): 1,
        ("effort", "agree"): 1,
    }


def test_the_shadow_counter_has_at_most_fifteen_series(
    roadmap: Roadmap, jev: JevFake, otlp: FakeCollector
) -> None:
    first = roadmap.issue("Cache embeddings")
    roadmap.issue("Keep embeddings cached")
    jev.picks = {f"duplicate_of_{first}": 0.95}
    roadmap.plan(_model(jev))
    jev.fail(503)
    roadmap.issue("Another idea")
    roadmap.plan(_model(jev))

    counts = _counts(otlp)

    assert {outcome for _, outcome in counts} <= {"agree", "differ", "jev_error"}
    assert {field for field, _ in counts} <= {"type", "priority", "value", "effort", "duplicate"}
    assert len(counts) <= 15
    assert ("duplicate", "differ") in counts


def test_shadow_counts_nothing_in_the_counter_of_the_deciding_model(
    roadmap: Roadmap, jev: JevFake, otlp: FakeCollector
) -> None:
    roadmap.issue("Cache embeddings")

    roadmap.plan(_model(jev))

    assert list(otlp.points(FIELDS_TOTAL)) == []


def test_a_metered_shadow_model_still_observes_and_counts_only_triage_calls(
    roadmap: Roadmap, jev: JevFake
) -> None:
    number = roadmap.issue("Cache embeddings")
    meter = SpendMeter()

    roadmap.run(meter.model(_model(jev)))

    assert _marks(roadmap, number) is not None
    assert meter.counts["model_calls"] == 1


def test_a_plain_model_records_no_mark(roadmap: Roadmap) -> None:
    number = roadmap.issue("Cache embeddings")

    roadmap.run(FakeModel(topics=("embeddings",)))

    assert _marks(roadmap, number) is None


def test_the_setting_builds_the_model_for_each_mode(
    config: Callable[..., Any], keyring_store: Any
) -> None:
    built = {}
    for mode in ("off", "shadow", "on"):
        config(roadmap={"intake": {"jev": mode}})
        built[mode] = type(build_intake_model())

    assert built == {
        "off": GatewayIntakeModel,
        "shadow": ShadowIntakeModel,
        "on": JevIntakeModel,
    }


def test_the_setting_is_off_by_default_and_refuses_the_old_bool() -> None:
    assert Settings().roadmap.intake.jev == "off"
    with pytest.raises(ValidationError) as raised:
        RoadmapIntakeConfig(jev=True)

    assert raised.value.errors()[0]["loc"] == ("jev",)
