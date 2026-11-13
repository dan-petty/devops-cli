# Design

## Decisions

- **One ceiling rule.** Each new setting, and `roadmap.stage.gate_returns`, has `le=CONST_ROADMAP_LIMIT_CEILING_FACTOR * <default>`, with the factor 4. One constant states the rule, so the descriptions say "4 times the default" and no number goes out of date. `verify_repair_rounds` takes 4 times the default of its ceiling setting (16), because the ceiling setting, and not its own default, bounds it.
- **The ceiling of the repair rounds is a setting.** `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` bounded both the setting and the rounds that follow it while a review fixes more findings than it adds. It becomes `roadmap.stage.verify_repair_rounds_ceiling` (default 4), and `repair_round_due` takes the ceiling as an argument. With no configuration, an item gets the same rounds as before. The live value `verify_repair_rounds: 4` loads with the default ceiling.
- **Read at each use, once for each unit of work.** The planner reads `roadmap.stage` when a round makes it, the toolbox client when it is made, the plan defect rule at each round, the fix-plan selection at each call, and the implement step when it starts (`ToolCallLog.limits`). A step uses one set of values from its start to its end, so a ConfigMap change in the middle of a step does not change its limits.
- **Pure functions take the limit as an argument.** `gate_extension(limit=...)`, `repair_round_due(ceiling=...)`, `progress_digest(calls, size)` and `extends(digest, max_refused)` read no settings. Their callers pass the values, so the tests of the rules need no configuration.
- **The usage limits default to None.** `run_step`, `run_fix_step` and `ToolboxClient` take `usage_limits=None` and build the limits from the settings (`step_usage_limits`, `run_limits`). A default of the signature is fixed at import, so it cannot follow a setting.
- **The prompts hold placeholders.** The call budget of a run is in the prompt text, so the prompts get `{{<setting>}}` placeholders, as the implement prompt does for its tables. `with_call_budget` fills them for the plan prompt and the review prompt. The text says "From call number N" in place of "From the Nth call", because a setting can give a number with no correct `th` suffix.
- **The file tools take the retries.** `Coder` gives its file tools 5 retries of their own, so the retries of the agent do not reach them. `_tune` replaces `max_retries` of the `FileSystem` capability with `tool_retries`.
- **Order checks name both settings.** One helper, `_check_nested`, raises `"<inner> must not be above <outer>"`. A field above its ceiling fails with the pydantic error, whose location names the full setting path.

## Rejected alternatives

- **Raise the constants.** A raised constant still needs a release for the next try, and the owner asked to try values until one works.
- **No ceiling.** A typo such as `gate_returns: 300` would give one item hundreds of plan runs. A ceiling of 4 times the default leaves room for two doublings.
- **New time order checks (tool time below step time below item time).** The issue asks to keep the order, and the existing check of the deadline settings holds the outer part. A new check of `command_timeout_seconds` and `step_time_limit_seconds` refuses settings that tests and people use today, such as a step limit of 60 s, so it is no part of this change.
- **Change the admission policy.** The policy `roadmap-service-jobs` is a security control, and the issue keeps it.
