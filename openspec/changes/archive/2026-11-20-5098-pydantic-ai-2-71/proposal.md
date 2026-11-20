# Proposal: #5098

## Why

`pyproject.toml` pins pydantic-ai 2.59.0 and pydantic-ai-harness 0.59.0. The newest releases are 2.71.0 and 0.71.0 (2026-11-19). Experiment 1 of #6519 runs the stock harness `Coder` as upstream runs it, and needs the 0.71 features. The move breaks run-time checks with no error (#5098): since 2.60 pydantic-ai builds no `RetryPromptPart`, so the run trace stops counting the schema violations of the output tool.

Closes #5098.

## What Changes

- Pin `pydantic-ai[spec]==2.71.0` and `pydantic-ai-harness[coder]==0.71.0`. The lock moves pydantic-ai-slim, pydantic-evals and pydantic-graph with them, and no other package.
- `RunTrace` and the investigation of refine find a retry with `is_retry`: the `ToolReturnPart` of a call with `outcome='retried'`, or a `RetryFeedbackPart`.
- The `DeferredToolRequests.build_results` override takes `answered_by`.
- The gateway call model sends a stream again when an error frame with code 408 comes before the first event. pydantic-ai 2.71 raises that frame as a `ModelTimeoutError`, which the model read as a timeout of the client.
- The step imports `FileSystem` from `pydantic_ai_harness.file_system`, its name since 0.69.
- `ToolCallLog` notes the call that `Coder` answers with a failed result (a `ToolFailed` after the retries of the tool) as failed, with its reason. So its Job log line and trace event stay, and the same call again gets the refusal of a repeated failed call (#3570).
- The provider rule of the failure classes takes an HTTP error of pydantic-ai by the class of its status category, such as `ModelRequestRejectedError: HTTP 400`, as it took `ModelHTTPError`.
- The description of `roadmap.implement.tool_retries` says that a spent retry comes back to the model as a failed result.
- `.github/renovate.json` holds google-genai below 3 no more: pydantic-ai 2.71 caps it below 3 itself.
- The ruff rule TID251 bans `RetryPromptPart` and `pydantic_ai_harness.filesystem`, so neither comes back.
- The tests take the retry parts from a recorded run of an agent (`refused_call`, `refused_output`, `refused_text` in `tests/support/model_script.py`), not from a hand-built `RetryPromptPart`.

The upgrade changes behavior that the change keeps as upstream gives it:

- `Coder` answers the call that spends the retries of a tool with the last error as a failed result, and the run goes on (0.65). So the reason of a step names no last retries, and that call counts as no retry. The `roadmap-implement-step/trace` delta states this.
- `Coder` has new base instructions (0.69), sends its tools with no strict schema (0.64), and protects the `.git` file of a worktree.
- A reply that the output token limit cuts with no output ends the run with `OutputTokenLimitExceeded`, a kind of `UnexpectedModelBehavior`, at once (2.68). The stop of refine names that class.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/budgets`: `tool_retries` bounds the retries of a tool; only arguments that break the schema of the tool then end the step.
- `roadmap-implement-step/trace`: a step goes on when a file tool spends its retries, so its reason names no last retries, and the call that `Coder` answers with a failed result counts as no retry.

## Impact

The roadmap jobs stage, implement, refine and alternatives run on pydantic-ai 2.71. Fits one pull request.

## Feasibility

PyPI names 2.71.0 and 0.71.0 as the newest releases. `uv lock` resolves them and keeps google-genai 2.34.0, tenacity 9.1.4, genai-prices 0.2.5 and openai 3.49.0. On 2.71.0, 18 tests of `tests/roadmap/stage`, `tests/roadmap/implement`, `tests/roadmap/refine`, `tests/roadmap/test_roadmap_alternatives.py` and `tests/ai` failed, and mypy found one error in `src/devops_cli/ai/tools/__init__.py`. The release notes of v2.60.0 to v2.71.0 name the changes above.

## Existing Tool Considered

pydantic-ai and pydantic-ai-harness themselves, MIT, maintained. `is_retry` of `pydantic_ai.messages` replaces the class checks. The change deletes the hold rule of `.github/renovate.json` and the hand-built retry parts of the tests.
