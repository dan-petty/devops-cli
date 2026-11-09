# Design

## Decisions

- **The setting is in the client, in the model of the Claude group.** `_claude_group_model` already holds the settings of every request to a Claude group (the output cap of #4220), so `parallel_tool_calls=False` goes there and covers every caller. It is not a new setting of the user: the Anthropic behavior does not change per host, so no ConfigMap changes.
- **The stop carries a typed field.** `InvestigationStopped.invalid_arguments` is true when the run ends with `UnexpectedModelBehavior` and a tool call of the last `ModelResponse` has arguments that `pydantic_core.from_json` refuses. It is read from the messages of the run and not from the text of the error. A stop with `invalid_arguments` has `schema_broken` false, because the cause is the arguments, as for `output_limit` (#4220).
- **`ToolboxClient` raises `RoadmapStageError` for it.** The error shows its masked text in the item record, as for the output limit. The message is written with no backticks, because `run_error_message` masks a code span of the stop text.

## Rejected alternatives

- **Split the joined arguments in the client.** Rejected: the rule of the project is to write no compensating code. The join is a fault of the gateway or of the model reply, and the setting stops the reply from holding several calls.
- **Bump the LiteLLM image.** Rejected for this change: v1.105.0 repairs the parse of joined arguments, not the join, and a bump of a pinned image is a change that a person makes. The change reports the version.
- **Set the Anthropic `disable_parallel_tool_use` in `k8s/llm/gateway/config.yaml`.** Rejected: the gateway entry would then apply it to every client of the group, and the client setting already covers the stage run. The client keeps the cause and the fix in one place with the output cap.
