# Design

## Decisions

- **The error carries the facts, the job reads them.** `AIClientError` gets `status: int | None` and `timed_out: bool` as keyword arguments, as `StructuredOutputValidationError` carries `violations`. The code that builds the error knows the status and the timeout. The warning then needs no parse of the message, which can quote the reply of the provider.
- **`reason` is the error code, then the status or `timeout`.** `AIClientError.reason` gives `LLM_INFERENCE_ERROR, HTTP 408 Request Timeout`, `LLM_INFERENCE_ERROR, timeout` or `LLM_INFERENCE_ERROR`. The phrase of a status comes from `http.client.responses`. It never holds the message.
- **The status is 408, not "1100 s".** The 1,100 s of the incident is in the body that LiteLLM wrote. The body is text of the gateway, and the project does not parse it. The status 408 states the same cause.
- **The pydantic-ai path sets the same fields.** `model_call_error` sets `status` for a `ModelHTTPError` and `timed_out` for a `ModelTimeoutError`. The investigation therefore reads like the proposal call.
- **`InvestigationStopped` keeps `reason` and gets `message`.** The alternatives job writes `reason` in its comment and its record. A longer reason would change that text and add the hint URL of `UsageLimitExceeded`. A separate field leaves the alternatives text as it is.
- **One helper makes the message.** `run_error_message` in `agent_run.py` takes `AgentRunError.message`, keeps its first line, masks the secrets and cuts it. The first line is cut before the masking, because the masking is slower than linear. The first line holds the fixed description, and the later lines of a validation error hold the reply.
- **The repository comes from the caller.** `plan_refine` has `repo`. It passes `repo` to `refine_one_item`, which passes it to `_investigate`, and to `_failed_item`. The store has no repository name in its protocol.
- **The error of the round, the record and the comments do not change.** `RoadmapRefineError` already names the class and the violation count. The issue asks for the warnings only.

## Rejected alternatives

- **Reuse `_stop_reason` of the implement step.** It builds its text from `str(stopped)`. For `UnexpectedModelBehavior` that text holds the `body`, which is model text. It also needs a `ToolCallLog`. A follow-up issue reports the leak.
- **Log `message` in full.** `models/openai.py` puts a pydantic `ValidationError` in the message, and its later lines quote the reply. The first line is safe.
- **Read the status from `__cause__`.** The cause is an `openai` or `httpx2` error, and a keepalive error frame has no status on its object: `_frame_status` reads it from the body. The mixins already know the status when they build the error.
- **Parse the status from the message.** The message is built for people and can hold the body of the reply. A parse is the hand-rolled code that AGENTS.md rules out.
- **A structured (JSON) log.** The Service writes plain text. The issue does not ask for a new format.
- **Add the reason to `RoadmapRefineError` and the record.** The issue asks for the warnings. The error and the record keep their text, so they cannot gain model text.
