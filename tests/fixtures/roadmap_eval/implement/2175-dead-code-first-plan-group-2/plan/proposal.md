# Proposal

## Why

Five functions and properties in src/ have no caller, no registering decorator, and no library override. They are the remainder of the dead-code audit of 2026-10-24. Issue #1910 deletes the other 17 names. These five are not in #1910 and must be deleted to remove dead code from the tree.

## What Changes

- Delete StreamingTokenProcessor.thinking_detected from src/devops_cli/ai/client/streaming.py
- Delete LLMClient._get_ollama_semaphore from src/devops_cli/ai/client/unified.py
- Delete ThinkingStreamProcessor.unique_thinking from src/devops_cli/ai/thinking_stream.py
- Delete _validation_error_key from src/devops_cli/config/settings.py
- Delete Dashboard.grid_width from src/devops_cli/grafana/schema.py
- Remove any exclusive import or constant that only a deleted name uses
- Remove any test that only calls a deleted name and name it in the pull request
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `thinking-stream`: unique-thinking-removed

## Impact

- Code: `src/devops_cli/ai/client/streaming.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/thinking_stream.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/grafana/schema.py`

## Feasibility

- The issue confirms each name is dead by git grep at b170358e. The context shows the definitions: thinking_stream.py shows unique_thinking, settings.py shows _validation_error_key, and schema.py shows grid_width.
- First check: run git grep -n -w thinking_detected src/ tests/ docs/ and confirm only the definition line appears.
- First check: run git grep -n -w _get_ollama_semaphore src/ tests/ docs/ and confirm only the definition line appears.
- First check: run git grep -n -w unique_thinking src/ tests/ docs/ and confirm only the definition line appears.
- First check: run git grep -n -w _validation_error_key src/ tests/ docs/ and confirm only the definition line appears.
- First check: run git grep -n -w grid_width src/ tests/ docs/ and confirm only the definition line appears.
- Final check: run uv run devops ci and confirm exit code 0 and coverage at or above fail_under.

## Existing Tool Considered

Not applicable. The change deletes five known dead definitions. No tool or library is needed to perform the deletion. The internal code deleted is StreamingTokenProcessor.thinking_detected, LLMClient._get_ollama_semaphore, ThinkingStreamProcessor.unique_thinking, _validation_error_key, and Dashboard.grid_width.
