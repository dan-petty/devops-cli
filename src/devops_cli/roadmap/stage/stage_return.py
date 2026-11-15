"""The bound on the earlier plan of a return request (#3529).

A return of the stage job sends the earlier plan back to the planner with the problem, after a gate
refused a reply or after the review returned a finding. A long earlier plan pushes that request past
the limit at which the run offers no tool, and the planner then makes no tool call, so it revises a
plan about code that it did not read. `request_tokens` measures the request as `_ask_plan` sends it,
and `bound_previous` cuts the texts of the earlier plan only when the measure passes the limit of
the tools less the reserve that the first request keeps.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from devops_cli.ai.context_budget import count_tokens, truncate_to_token_limit
from devops_cli.config.constants import CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS
from devops_cli.roadmap.refine.refine_investigation import tool_stop

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_request import StageRequest

# The share of its own length that each text keeps at the first cut, the halves after it while the
# measured request still passes the target, and the most cuts that one bound makes.
_FIRST_SHARE: Final[float] = 0.5
_HALVINGS: Final[int] = 20
# A text of at most this many tokens stays whole: it is a path, a name or a command of the plan,
# and a cut path would give the planner nothing to revise.
_KEPT_TOKENS: Final[int] = 64

__all__ = ["bound_previous", "request_tokens"]


def request_tokens(request: Mapping[str, Any]) -> int:
    """The tokens of `request` as the planner reads it: the JSON text that `_ask_plan` sends."""
    return count_tokens(json.dumps(request, ensure_ascii=False, indent=1))


def bound_previous(
    request: StageRequest, previous: Mapping[str, Any], problem: str, window: int
) -> dict[str, Any]:
    """`request` for the model, with the earlier plan `previous` and `problem`, for a run of
    `window` tokens. The earlier plan keeps every key, every path and its summary, and its texts are
    cut only when the full request passes the limit of the tools less the reserve of the first
    request, so the planner keeps its tools."""
    full = {**request.for_model(), "previous": dict(previous), "problem": problem}
    target = tool_stop(window) - CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS
    bounded = full
    share = _FIRST_SHARE
    for _ in range(_HALVINGS):
        if request_tokens(bounded) <= target:
            break
        bounded = {**full, "previous": _bounded(previous, share)}
        share /= 2
    return bounded


def _bounded(value: Any, share: float) -> Any:
    """`value` with each text cut to `share` of its own length. A key, a number and a bool stay, and
    so does a text of at most `_KEPT_TOKENS` tokens, which is a path, a name or a command."""
    if isinstance(value, str):
        tokens = count_tokens(value)
        if tokens <= _KEPT_TOKENS:
            return value
        return truncate_to_token_limit(value, max(1, int(tokens * share)))
    if isinstance(value, Mapping):
        return {key: _bounded(item, share) for key, item in value.items()}
    if isinstance(value, list):
        return [_bounded(item, share) for item in value]
    return value
