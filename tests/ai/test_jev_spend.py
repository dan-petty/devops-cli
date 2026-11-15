"""A Jev decision call records its tokens and cost in the spend ledger (#4296).

A Jev call runs no Agent, so the spend hook of `build_agent` never sees it. The call now goes
through `record_jev_spend`, which prices the answer at the Jev price of the pricing registry.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.models.decision import ChoiceQuestion, DecisionRequest

from devops_cli.ai.jev import decide_with_jev
from devops_cli.ai.spend import ledger as ledger_module
from devops_cli.ai.spend.ledger import SpendLedger, get_spend_ledger, reset_spend_ledger
from devops_cli.ai.spend.pricing import PricingRegistry, reset_pricing_registry
from devops_cli.config.constants import CONST_AI_JEV_MODEL

if TYPE_CHECKING:
    from tests.support.fakes.jev import JevFake

REQUEST = DecisionRequest(
    state={"title": "Record the cost"},
    questions={"pick": ChoiceQuestion(instructions="Which?", criteria={"a": "A", "b": "B"})},
)
# The answer of `JevFake`: 64 input tokens and one output token per answer. The ledger keeps
# the cost at 6 decimal places, so 2.688e-6 USD becomes 3e-6.
PROMPT_TOKENS = 64
JEV_PRICE_USD = round(PROMPT_TOKENS * 0.042 / 1_000_000, 6)


@pytest.fixture
def ledger(isolate_data_dir: Path) -> Iterator[SpendLedger]:
    """The spend ledger of an isolated data directory."""
    reset_spend_ledger()
    reset_pricing_registry()
    yield get_spend_ledger()
    reset_spend_ledger()
    reset_pricing_registry()


def test_one_jev_call_records_its_tokens_and_price(jev: JevFake, ledger: SpendLedger) -> None:
    decide_with_jev(REQUEST, model=jev.model)

    (row,) = ledger.get_lifetime_report(group_by="model").models

    assert (
        row.model,
        row.prompt_tokens,
        row.request_count,
        round(row.approx_spend_usd, 12),
    ) == (CONST_AI_JEV_MODEL, PROMPT_TOKENS, 1, JEV_PRICE_USD)


def test_the_cost_report_lists_the_jev_model(
    jev: JevFake,
    ledger: SpendLedger,
    cli: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.commands import ai_cost

    monkeypatch.setattr(ai_cost, "get_spend_ledger", lambda: ledger)
    decide_with_jev(REQUEST, model=jev.model)

    result = cli("ai", "cost", "report", "--by", "model", "--format", "json")

    assert (result.exit_code, CONST_AI_JEV_MODEL in result.stdout) == (0, True)


def test_a_ledger_that_fails_leaves_the_answer(
    jev: JevFake, ledger: SpendLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(**_: object) -> None:
        raise OSError("the disk is full")

    monkeypatch.setattr(ledger_module, "track_request_spend", fail)

    response = decide_with_jev(REQUEST, model=jev.model)

    assert (response.model_name, response.usage.input_tokens) == (CONST_AI_JEV_MODEL, PROMPT_TOKENS)


def test_a_workstation_with_no_setting_prices_the_jev_model(tmp_path: Path) -> None:
    """The registry holds the Jev price, so no setting and no file are needed (#4296)."""
    registry = PricingRegistry(data_dir=tmp_path)

    cost = registry.calculate_request_cost(
        CONST_AI_JEV_MODEL,
        1_000_000,
        1_000_000,
        server=CONST_AI_JEV_MODEL,
        provider="gateway",
        served_model=CONST_AI_JEV_MODEL,
    )

    assert (round(cost.cost_usd, 6), cost.pricing_source) == (
        0.042,
        "builtin:hosted_group_prices",
    )
