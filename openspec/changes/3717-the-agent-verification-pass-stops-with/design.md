# Design

## Decisions

- **Read the findings from the text of the replies of a stopped run with `_repair_and_validate_payload`.**: The text of a reply is already in the run's messages, and the parser already validates a reply against the schema and has its own test.
- **Type the stop from the run's messages and not from the message text.**: `run_error_message` hides each quoted part, so the message names no tool and no limit.
- **Set the typed reason on the `RunTrace` of the run.**: A review stop raises `RoadmapStageError` or `StructuredOutputValidationError`, and the eval already keeps the trace for its tool answers.
- **Add `reason` to `CaseOutcome` and `cases[].reason` to the report, and keep `error`.**: A typed field lets the text report and a test read the cause without parsing the message.
- **Keep `CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES` at 2.**: Each retry costs about five minutes and does not make a model call the output tool.
- **Accept a text reply for `Verification` and `LaterVerification` only.**: The plan run's text reply is a tested schema violation, and the issue is about the verification pass.

## Rejected alternatives

- **Raise the output retry limit.**: `src/devops_cli/config/constants.py:3378:CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES: Final[int] = 2` is the limit, and each retry costs about five minutes.
- **Set the agent's output type to the union of the schema and `str`.**: `src/devops_cli/roadmap/refine/refine_investigation.py:def investigate` returns the schema for every caller, and a union accepts an intermediate text reply as the output before the tools run; the pydantic-ai documents are not in this repository, so this run did not check the mode.
- **Parse the masked message text for the cause.**: `src/devops_cli/roadmap/agent_run.py:148:hidden = _QUOTED.sub("<text>", bounded_text(first))` hides the tool name, so the message holds `<text>`.
- **Write the reason into `error` only.**: `src/devops_cli/roadmap/stage/stage_verify_eval.py:104:error: str = ""` is a free string, so a test and a person must parse it.
