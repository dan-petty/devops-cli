# Design

## Decisions

- **Set the profile where the model is built.** `infer_model` takes no profile, so for a Claude group on a gateway `_resolve_remote_inferred_model` builds `OpenAIChatModel(target, provider=..., profile={"supports_forced_tool_choice": False})` with the same provider factory, and keeps `served_by`. A Claude group is a target that starts with `claude-`. `get_task_model` and `get_tier_model` both go through `resolve_pydantic_ai_model`, so one place covers every caller.
- **Use the current profile key.** `supports_forced_tool_choice` replaces the deprecated `openai_supports_tool_choice_required` of the issue text.
- **Count in `record_run_spend`.** Every agent run of a roadmap Job ends there, with all replies in hand. It reads the distinct `model_name` of the replies, passes the answered model as `served_model` to `track_request_spend`, and emits one count for each reply under its answered model.
- **Fallback test.** The answered model equals the asked model, or ends with `/` and the asked model (a provider prefix, also for a name that holds a slash). Any other name is a fallback. A reply with no model name adds no count.
- **Spend record.** One record covers the run. When all replies name one model, that model is `served_model`. When they differ, the model of the last reply is `served_model`; the counter holds the full split.

## Rejected alternatives

- **Change the gateway fallback.** The fallback hides the 400, but a person decides it (issue note). The new counter makes the hidden fallback visible instead.
- **Use `openai_supports_tool_choice_required`.** pydantic-ai 2.59.0 raises `PydanticAIDeprecationWarning` for it, tested with warnings as errors.
- **Switch the planner to text output or prompted output.** It changes the output contract of every stage for one model group; the profile key keeps the tool output.
- **Detect the fallback from the gateway response headers.** The `model` field of the reply is the library's own data (`ModelResponse.model_name`), so no header parser is needed.
