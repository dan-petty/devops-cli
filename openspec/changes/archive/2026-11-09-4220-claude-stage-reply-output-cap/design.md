# Design

## Decisions

- **The cap is in the client, as a constant.** `_claude_group_model` passes `ModelSettings(max_tokens=CONST_AI_CLAUDE_GROUP_MAX_OUTPUT_TOKENS)` to `OpenAIChatModel`, so every caller of a Claude group gets it, as the implement step (#2869) does for its agent. It is a constant and not a setting: the model limit does not change per host, so no ConfigMap rollout is needed. The value 32,000 is about 8 times the Anthropic default, is large enough for a `StageProposal` and the thinking tokens, and is far under the 128,000 output tokens of `claude-sonnet-5-5`.
- **The stop carries a typed field.** `InvestigationStopped.output_limit` is true when the run ends with `UnexpectedModelBehavior` and the last `ModelResponse` has `finish_reason` `length`. The field is read from the library's finish reason, and not from the text of the error. It also covers a reply that holds a part but is cut, which then fails the schema twice. A stop with `output_limit` has `schema_broken` false, because the model did not break the rules of the output: the provider cut the reply.
- **`ToolboxClient` raises `RoadmapStageError` for it.** `_failure_of` shows the text of a `RoadmapStageError` (masked) and the count of violations of a `StructuredOutputValidationError` only, so the message reaches the item record and the log. The message is written with no backticks, because `run_error_message` masks a code span of the stop text.

## Rejected alternatives

- **Put `max_tokens` in `litellm_params` of the gateway entry.** Rejected: it is not verified that LiteLLM applies it as a default (LiteLLM is not in the venv), and the issue asks not to copy the cap to both places. The client cap covers every caller of the group that goes through `resolve_pydantic_ai_model`.
- **A `Hooks` capability that raises `OutputCapReached` after a reply with `finish_reason` `length` (the implement step).** Rejected: the stage run already ends in `UnexpectedModelBehavior`, and `investigate` already builds `InvestigationStopped` from it, so one typed field is the smaller change. A hook would add a second error path in `investigate`, which refine also uses.
- **Count the violations differently (read the text of the retry prompt).** Rejected: it parses a message, and the count would still hide the length stop.
