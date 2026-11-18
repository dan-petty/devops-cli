# Design

## Decisions

- **Type the stop of a run from the messages of the run and not from the text of its message.**: `run_error_message` hides each quoted part, so the message names no tool and no limit that a person can act on.
- **Name the tools retry limit and the output retry limit that the run used, and not a fixed constant.**: Check the limit that the run used, read from the constant by name or set by the test.
- **Read the tool name of a refused call from the last reply of the run.**: The masked message hides it, and `RunTrace.absorb` records no call to a tool that is not a function tool of the run.
- **Check the limit that ended the tools before the refused call.**: The `_offering` hook takes the tools away at a limit, and the call after it gets the same tool retry stop, so the limit is the cause that a person can act on.
- **Rely on pydantic-ai `AutoOutputSchema` for valid text replies.**: `_output.py:638-655` already parses JSON and strips Markdown fences (`_output.py:981`). Keep `text_reply` only for text that pydantic-ai refuses.
- **Accept a text reply for `Verification` and `LaterVerification` only.**: The plan run's text reply is a tested schema violation, and the issue is about the verification pass.
- **Set the typed reason on the `RunTrace` of the run and read it in the eval.**: A stopped review raises an error, and the trace is the record that the eval already keeps for each run of a case.

## Rejected alternatives

- **Home-grown parser with `_repair_and_validate_payload` for text replies.**: pydantic-ai `AutoOutputSchema` already parses plain and fenced JSON text replies; a custom parser violates project rule 3.
- **Read the observed stop as a text reply in place of the output tool.**: `src/devops_cli/roadmap/stage/stage_verify.py:82:_REPLY_RETURNS: Final[int] = 1` sets the output retry limit to 1, while the message of the issue names 2, which is `src/devops_cli/roadmap/refine/refine_investigation.py:612:"tools": CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES,` and `src/devops_cli/config/constants.py:3378:CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES: Final[int] = 2`.
- **Raise the output retry limit of the verification pass.**: `src/devops_cli/roadmap/stage/stage_verify.py:82:_REPLY_RETURNS: Final[int] = 1` is the limit, and each retry costs about five minutes of the run.
- **Parse the masked text of the message for the cause.**: `src/devops_cli/roadmap/agent_run.py:148:hidden = _QUOTED.sub("<text>", bounded_text(first))` hides the tool name, so the message holds `<text>`.
- **Write the reason into `error` only.**: `src/devops_cli/roadmap/stage/stage_verify_eval.py:104:error: str = ""` is a free string, so a test and a person must parse it.
