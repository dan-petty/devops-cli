"""Native Pydantic AI result subsystem for devops-cli.

Provides unified execution result handling, streaming results, usage tracking,
dynamic model pricing calculation, and output validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai._cost import best_effort_price
from pydantic_ai._output import (
    OutputSchema,
    OutputValidator,
    TextOutputSchema,
    run_image_process_hooks,
    run_output_with_hooks,
)
from pydantic_ai._sync_stream import SyncStreamBridge
from pydantic_ai.messages import AgentStreamEvent
from pydantic_ai.result import (
    AgentStream,
    FinalResult,
    OutputValidatorFunc,
    StreamedRunResult,
    StreamedRunResultSync,
)
from pydantic_ai.usage import RunUsage

if TYPE_CHECKING:
    from devops_cli.ai.agents.models import AgentResponse


def create_run_usage(
    input_tokens: int = 0,
    output_tokens: int = 0,
    requests: int = 0,
    tool_calls: int = 0,
    **kwargs: Any,
) -> RunUsage:
    """Construct a native RunUsage tracking instance with token and call metrics."""
    return RunUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        requests=requests,
        tool_calls=tool_calls,
        **kwargs,
    )


def calculate_usage_cost(
    usage: RunUsage | Any,
    model_name: str | None = None,
    **kwargs: Any,
) -> Any:
    """Calculate live financial cost for an execution run using native best_effort_price."""
    if usage is None or model_name is None:
        return None

    run_u: RunUsage
    if isinstance(usage, RunUsage):
        run_u = usage
    else:
        in_tok = getattr(usage, "input_tokens", 0)
        out_tok = getattr(usage, "output_tokens", 0)
        reqs = getattr(usage, "requests", 1)
        tc = getattr(usage, "tool_calls", 0)
        run_u = RunUsage(input_tokens=in_tok, output_tokens=out_tok, requests=reqs, tool_calls=tc)

    try:
        return best_effort_price(run_u, model_name=model_name, **kwargs)
    except Exception:
        return None


def to_final_result(
    output: Any,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
) -> FinalResult[Any]:
    """Wrap structured data or text into a native FinalResult marker container."""
    return FinalResult(output=output, tool_name=tool_name, tool_call_id=tool_call_id)


def to_agent_response(result: Any) -> AgentResponse[Any]:
    """Universal converter transforming native Pydantic AI results into an AgentResponse container."""
    from devops_cli.ai.agents.models import AgentResponse

    if isinstance(result, AgentResponse):
        return result

    if isinstance(result, FinalResult):
        output = result.output
        content = str(output)
        data = output if not isinstance(output, str) else None
        return AgentResponse(content=content, data=data)

    return AgentResponse.from_run_result(result)


__all__ = [
    "AgentStream",
    "AgentStreamEvent",
    "FinalResult",
    "OutputSchema",
    "OutputValidator",
    "OutputValidatorFunc",
    "RunUsage",
    "StreamedRunResult",
    "StreamedRunResultSync",
    "SyncStreamBridge",
    "TextOutputSchema",
    "best_effort_price",
    "calculate_usage_cost",
    "create_run_usage",
    "run_image_process_hooks",
    "run_output_with_hooks",
    "to_agent_response",
    "to_final_result",
]
