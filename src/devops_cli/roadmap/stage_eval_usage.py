"""The tokens and the spend of a live run of the golden set (#3207).

The spend ledger is the one place that every model call passes through, the calls of the agent
runs included. A run shows each recorded call to `RunUsage.add` and sums its tokens. The ledger
prices a call that a gateway serves from the reply headers, and a pydantic-ai run carries none, so
the run is priced here once, at the hosted price of the model by name, with the price registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from devops_cli.config.constants import CONST_PRICING_SOURCE_UNKNOWN


@dataclass
class RunUsage:
    """The tokens and the spend of a run."""

    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, call: dict[str, Any]) -> None:
        """Count one recorded model call. A call that the response cache answered ran no model."""
        if call.get("cached"):
            return
        self.input_tokens += int(call.get("prompt_tokens") or 0)
        self.output_tokens += int(call.get("completion_tokens") or 0)

    def spend_usd(self, model: str) -> float | None:
        """The spend of the run at the hosted price of `model`, or None when no price is known."""
        from devops_cli.ai.spend.pricing import get_pricing_registry

        cost = get_pricing_registry().calculate_request_cost(
            model, self.input_tokens, self.output_tokens
        )
        return None if cost.pricing_source == CONST_PRICING_SOURCE_UNKNOWN else cost.cost_usd
