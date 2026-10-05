# Task: Sequential Pipeline Stages Carry Budgeted Context With Single Scratchpad (#859)

**Issue**: [#859](https://github.com/dan-petty/devops-cli/issues/859)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-important
**Scope**: scope/ai

## Description
Prior to this change, `MultiAgentPipeline` accumulated previous stage outputs and re-appended the entire scratchpad summary on each iteration. By stage 5, prompts carried duplicate scratchpad sections and unbounded context (e.g. 5,786 tokens for 8K replies).

This change establishes bounded context budgeting for sequential pipelines:
1. **Context Budgeting**: Adds `DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS: int = 4096` in `defaults.py`, configurable via constructor or `--stage-context-tokens` CLI option. Setting 0 disables the budget.
2. **Newest-First Allocation**: Previous outputs are budgeted newest-first. When older stages exceed the budget, they are truncated with visible marker `\n...[stage output truncated to the stage context budget]` or listed by name only as `### Stage {idx} ({name}) Output: omitted, over budget`. Stages are rendered in chronological stage order.
3. **Single Scratchpad Summary**: `ScratchpadBuffer.render_context_summary()` is appended once, after the carried outputs block, outside the budget.
4. **Recorded Metrics**: `PipelineStepResult` tracks `context_tokens` (exact token count of carried context sent to the stage) and `context_truncated` (boolean indicating if any carried output was cut).
5. **Bugfix**: Forwards `skip_rag` from `MultiAgentPipeline.run` to `agent.run(...)` and from `devops ai pipeline` CLI command (`skip_rag=not rag`).

## Offline Measurement Snippet

```python
from unittest.mock import MagicMock, patch
from devops_cli.ai.client import LLMClient
from devops_cli.ai.agents import MultiAgentPipeline, PydanticAgent
from devops_cli.ai.context_budget import count_tokens


def measure_pipeline(num_stages: int, chars: int, stage_context_tokens: int = 4096):
    sent_prompts = []

    def fake_chat(_system, messages, **_kwargs):
        sent_prompts.append(messages[-1].content)
        return ("Finding: " + "x" * 70 + "\n") * (chars // 80)

    client = MagicMock(spec=LLMClient)
    client.chat_messages.side_effect = fake_chat

    agents = [
        PydanticAgent(client=client, name=f"Agent{i}", system_prompt=f"Agent {i}")
        for i in range(1, num_stages + 1)
    ]
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        pipeline = MultiAgentPipeline(agents=agents, stage_context_tokens=stage_context_tokens)
        pipeline.run("Analyze workspace")

    return [(count_tokens(p), p.count("### Scratchpad Reasoning Context")) for p in sent_prompts]
```

### Context Tokens and Scratchpad Count Per Stage

Format per stage: `(prompt_tokens, scratchpad_count)`

| Case (Stages, Reply Chars) | Base / Before Implementation | Branch / After Implementation |
|:---|:---|:---|
| (5, 1000) | `[(2, 0), (241, 1), (514, 2), (837, 3), (1210, 4)]` | `[(2, 0), (241, 1), (457, 1), (673, 1), (889, 1)]` |
| (5, 4000) | `[(2, 0), (735, 1), (1502, 2), (2319, 3), (3186, 4)]` | `[(2, 0), (735, 1), (1445, 1), (2155, 1), (2865, 1)]` |
| (5, 8000) | `[(2, 0), (1385, 1), (2802, 2), (4269, 3), (5786, 4)]` | `[(2, 0), (1385, 1), (2745, 1), (4105, 1), (4324, 1)]` |
| (3, 4000) | `[(2, 0), (735, 1), (1502, 2)]` | `[(2, 0), (735, 1), (1445, 1)]` |

## Acceptance Criteria
- [x] Budget holds: 5-stage pipeline under 2048 budget keeps prompt context <= 2048, keeps stage 4 verbatim in stage 5, and cuts stage 1.
- [x] Scratchpad once: every stage prompt from stage 2 onward contains `### Scratchpad Reasoning Context` exactly once.
- [x] Budget off: `stage_context_tokens=0` carries every earlier reply verbatim without truncation.
- [x] Default is 4096: `DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS == 4096` and `MultiAgentPipeline` defaults to it.
- [x] Recorded metrics: `PipelineStepResult.context_tokens` matches count of carried context sent and `context_truncated` is recorded accurately.
- [x] CLI support: `devops ai pipeline` supports `--stage-context-tokens` and lists it in `--dry-run` output.
- [x] `skip_rag` forwarded: `agent.run(..., skip_rag=skip_rag)` correctly receives argument.
- [x] Parallel execution untouched: parallel pipeline tests continue to pass without regression.
- [x] Changelog fragment `changelog.d/859.md` written.
- [x] All 10 gates in `uv run devops ci` pass with 100% green status.

## Deliverables
- [x] `src/devops_cli/config/constants.py` updated with `CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX`.
- [x] `src/devops_cli/config/defaults.py` updated with `DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS`.
- [x] `src/devops_cli/lang/en/help.py` updated with `pipeline_stage_context_tokens`.
- [x] `src/devops_cli/ai/agents/pipeline.py` updated with newest-first allocation and single scratchpad summary.
- [x] `src/devops_cli/commands/ai.py` updated with `--stage-context-tokens`, dry-run output, and `skip_rag=not rag`.
- [x] `tests/test_pipeline_context_budget.py` unit and contract test suite.
- [x] `tests/test_ai_cmd.py` updated for dry-run verification.
- [x] `changelog.d/859.md` changelog fragment.
- [x] `docs/agent/tasks/task-859-pipeline-stage-context-budgets.md` task document.
