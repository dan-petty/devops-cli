"""The labelled set, the score and the command of the Jev completeness eval (#4308).

The web is faked at its edge: Jev answers the one request of each case on the gateway route.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.jev import create_jev_model
from devops_cli.config.constants import (
    CONST_ROADMAP_JEV_EVAL_MIN_CASES,
    CONST_ROADMAP_JEV_EVAL_MIN_CASES_PER_LABEL,
    CONST_ROADMAP_JEV_MAX_DIFF_TOKENS,
)
from devops_cli.config.settings import Settings
from devops_cli.roadmap.jev_completeness import Completeness, CompletenessOutcome
from devops_cli.roadmap.jev_completeness_eval import (
    CASES_DIRECTORY,
    CaseResult,
    Label,
    load_cases,
    rates,
    render,
    report_json,
    run_cases,
    switch_stays_off,
)
from tests.support.fakes.http import WebFake
from tests.support.paths import REPO_ROOT

GATEWAY = "http://example.com:4000/v1"
ROUTE = f"{GATEWAY}/systemone"
Cli = Callable[..., Any]


@pytest.fixture(autouse=True)
def _gateway_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")


def _settings() -> Settings:
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = GATEWAY
    return settings


def _case(folder: Path, name: str, label: str, criteria: list[str]) -> None:
    case = folder / name
    case.mkdir(parents=True)
    meta = {"id": name, "kind": "plan", "label": label, "source": {}, "criteria": criteria}
    (case / "case.json").write_text(json.dumps(meta), encoding="utf-8")
    (case / "draft.diff").write_text("+- [ ] 1.1 Keep every comment\n", encoding="utf-8")


def _answer(probabilities: list[float], tests: float = 2.0) -> dict[str, Any]:
    levels = {str(level): 0.0 for level in range(4)}
    levels[str(round(tests))] = 1.0
    answers: dict[str, Any] = {
        f"criterion_{n}": {"type": "noul", "noul": p, "confidence": 0.9}
        for n, p in enumerate(probabilities, start=1)
    }
    answers["tests"] = {
        "type": "score",
        "score": float(round(tests)),
        "probabilities": levels,
        "confidence": 0.9,
    }
    return {
        "model": "typesafe/jev-1.14",
        "answers": answers,
        "usage": {"input_tokens": 1_000_000, "output_tokens": 1},
    }


def _result(label: Label, probabilities: tuple[float, ...], tests: float = 2.0) -> CaseResult:
    held = any(p < 0.5 for p in probabilities)
    outcome = CompletenessOutcome.HELD if held else CompletenessOutcome.PASSED
    return CaseResult(
        "x", label, "plan", Completeness(outcome, (), probabilities, tests, input_tokens=100)
    )


def test_the_cases_load_with_their_diff_in_the_order_of_their_names(tmp_path: Path) -> None:
    _case(tmp_path, "b-complete", "complete", ["c"])
    _case(tmp_path, "a-incomplete", "incomplete", ["c", "d"])

    cases = load_cases(tmp_path)

    assert [(c.id, c.label, len(c.criteria)) for c in cases] == [
        ("a-incomplete", Label.INCOMPLETE, 2),
        ("b-complete", Label.COMPLETE, 1),
    ]
    assert cases[0].diff.startswith("+- [ ] 1.1")


def test_the_rates_count_the_held_cases_of_each_label_and_leave_out_unanswered_cases() -> None:
    failed = CaseResult(
        "e", Label.COMPLETE, "plan", Completeness(CompletenessOutcome.ERROR, reason="boom")
    )
    results = [
        _result(Label.INCOMPLETE, (0.1,)),
        _result(Label.INCOMPLETE, (0.9,)),
        _result(Label.COMPLETE, (0.9,)),
        _result(Label.COMPLETE, (0.2,)),
        _result(Label.COMPLETE, (0.8,), tests=0.0),
        failed,
    ]

    with_tests = rates(results, 0.5, tests=True)
    criteria_only = rates(results, 0.5, tests=False)

    assert (with_tests.recall, with_tests.complete, with_tests.held_complete) == (0.5, 3, 2)
    assert (criteria_only.held_complete, criteria_only.false_hold_rate) == (1, pytest.approx(1 / 3))


def test_the_switch_stays_off_on_a_small_set_and_on_too_many_false_holds() -> None:
    small = [_result(Label.INCOMPLETE, (0.1,)), _result(Label.COMPLETE, (0.9,))]
    big = [_result(Label.INCOMPLETE, (0.1,)) for _ in range(15)]
    clean = [*big, *[_result(Label.COMPLETE, (0.9,)) for _ in range(15)]]
    leaky = [*big, *[_result(Label.COMPLETE, (0.1,)) for _ in range(3)], *clean[15:]]

    assert (
        len(switch_stays_off(small)),
        switch_stays_off(clean),
        len(switch_stays_off(leaky)),
    ) == (
        1,
        [],
        1,
    )
    assert "too small" in switch_stays_off(small)[0]
    assert "false holds" in switch_stays_off(leaky)[0]


def test_a_run_asks_jev_once_for_each_case_and_reports_the_rates_and_the_spend(
    tmp_path: Path, web: WebFake
) -> None:
    _case(tmp_path, "a-incomplete", "incomplete", ["one"])
    _case(tmp_path, "b-complete", "complete", ["one"])
    web.respond("POST", ROUTE, 200, _answer([0.9]))

    results = run_cases(
        load_cases(tmp_path), new_model=lambda: create_jev_model(settings=_settings())
    )
    text = render(results, model="typesafe/jev-1.14", gateway=GATEWAY)
    report = json.loads(
        report_json(results, model="typesafe/jev-1.14", gateway=GATEWAY, taken="2026-11-10")
    )

    assert len(web.recorded) == 2
    assert "Recall of incomplete drafts (held): 0 of 1 (0%)" in text
    assert "False holds (complete drafts held): 0 of 1 (0%)" in text
    assert "Spend: 0.0840 USD" in text
    assert "stays off" in text
    assert [(c["id"], c["probabilities"]) for c in report["cases"]] == [
        ("a-incomplete", [0.9]),
        ("b-complete", [0.9]),
    ]


def test_the_committed_set_is_large_labelled_and_fits_the_window() -> None:
    cases = load_cases(REPO_ROOT / CASES_DIRECTORY)

    labels = [c.label for c in cases]
    assert len(cases) >= CONST_ROADMAP_JEV_EVAL_MIN_CASES
    assert all(labels.count(label) >= CONST_ROADMAP_JEV_EVAL_MIN_CASES_PER_LABEL for label in Label)
    assert all(c.criteria and c.diff.strip() for c in cases)
    assert len({c.id for c in cases}) == len(cases)
    assert all(count_tokens(c.diff) <= CONST_ROADMAP_JEV_MAX_DIFF_TOKENS for c in cases)


def test_a_removed_hunk_case_has_the_diff_of_its_complete_twin_less_one_hunk() -> None:
    cases = {c.id: c for c in load_cases(REPO_ROOT / CASES_DIRECTORY)}
    removed = [c for c in cases.values() if c.removed]

    assert removed
    for case in removed:
        assert case.removed is not None
        twin = cases[case.id.replace("-hunk-removed", "-complete")]
        assert (case.label, twin.label) == (Label.INCOMPLETE, Label.COMPLETE)
        assert case.removed["hunk"] in twin.diff
        assert case.removed["hunk"] not in case.diff
        assert len(case.diff) < len(twin.diff)


def test_the_command_lists_the_requests_of_a_dry_run_and_makes_none(cli: Cli, web: WebFake) -> None:
    result = cli("roadmap", "eval", "completeness", "--dry-run", "--limit", "2")

    assert result.exit_code == 0, result.output
    assert "no request was made" in result.output
    assert "/systemone" in result.output
    assert web.recorded == []


def test_the_command_stores_the_report_and_prints_the_rates(
    cli: Cli, tmp_path: Path, web: WebFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    _case(tmp_path, "a-incomplete", "incomplete", ["one"])
    _case(tmp_path, "b-complete", "complete", ["one"])
    web.respond("POST", ROUTE, 200, _answer([0.9]))
    monkeypatch.setenv("DEVOPS_CLI_AI_PROVIDER", "gateway")
    monkeypatch.setenv("DEVOPS_CLI_AI_GATEWAY_URL", GATEWAY)

    result = cli("roadmap", "eval", "completeness", "--cases", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert "Recall of incomplete drafts" in result.output
    assert "Stored the report in" in result.output
    assert len(web.recorded) == 2
