# Design

## Decisions

- **The error carries the facts, the job reads them.** `AIClientError` gets `status: int | None` and `timed_out: bool` as keyword arguments, as `StructuredOutputValidationError` carries `violations`. The code that builds the error knows the status and the timeout. The warning then needs no parse of the message, which can quote the reply of the provider.
- **`reason` is the error code, then the status or `timeout`.** `AIClientError.reason` gives `LLM_INFERENCE_ERROR, timeout (HTTP 408 Request Timeout)`, `LLM_INFERENCE_ERROR, timeout`, `LLM_INFERENCE_ERROR, HTTP 529` or `LLM_INFERENCE_ERROR`. The statuses 408 and 504 say that the call ran out of time, so the word `timeout` is there for them, as the issue asks. The phrase of a status comes from `http.client.responses`. It never holds the message.
- **Every provider sets the facts.** The gateway, Claude and Ollama paths set `status` and `timed_out`: `UnifiedMixin._connection_error` reads the httpx2 timeout, the OpenAI and Anthropic SDK mappings read their `APITimeoutError`, the Ollama status branches pass the status, and `_read_failures` of a stream reads the timeout. One reason text then serves every provider.
- **The status is 408, not "1100 s".** The 1,100 s of the incident is in the body that LiteLLM wrote. The body is text of the gateway, and the project does not parse it. The status 408 states the same cause.
- **The pydantic-ai path sets the same fields.** `model_call_error` sets `status` for a `ModelHTTPError` and `timed_out` for a `ModelTimeoutError`. The investigation therefore reads like the proposal call.
- **`InvestigationStopped` keeps `reason` and gets `message`.** The alternatives job writes `reason` in its comment and its record. A longer reason would change that text and add the hint URL of `UsageLimitExceeded`. A separate field leaves the alternatives text as it is.
- **One helper makes the text.** `bounded_text` in `agent_run.py` masks and cuts a text to `CONST_ROADMAP_RUN_ERROR_CHARS`. The text is cut before the masking, which is slower than linear, and after it, so a cut cannot split a secret. The implement step (#2758) and refine use it, so the limit lives in one place.
- **A warning keeps the fixed description of the message.** `run_error_message` takes `AgentRunError.message`, not `str()`. pydantic-ai writes data of the reply after some marks: the id of a tool call after `;`, the name of a tool in quotes, the repr of a part after `=`. So the helper keeps the first line, replaces each quoted part with `<text>`, stops at the first `:`, `;` or `=`, and drops the characters that cannot print. The text before those marks is the fixed description, such as `Exceeded maximum output retries (3)`.
- **The implement step reads `message` too.** `_stop_reason` used `str(stopped)`, which adds the `body` of an `UnexpectedModelBehavior`, the text of the model (#2778). It now uses `bounded_text(stopped.message)`. It keeps the whole message, as before, because the reason is for the owner and the message is a fixed text there.
- **The repository comes from the caller.** `plan_refine` has `repo`. It passes `repo` to `refine_one_item`, which passes it to `_investigate`, and to `_failed_item`. The store has no repository name in its protocol.
- **The error of the round, the record and the comments do not change.** `RoadmapRefineError` already names the class and the violation count. The issue asks for the warnings only.

## Rejected alternatives

- **Log `message` in full, or its first line.** `models/openai.py` puts a pydantic `ValidationError` in the message, and its later lines quote the reply. The first line can hold data too (a tool call id, a tool name), so the helper stops at the marks that start such data.
- **A list of the fixed descriptions.** A list of the messages that pydantic-ai can raise would break at each new release. The cut at the marks needs no list.
- **Read the status from `__cause__`.** The cause is an `openai` or `httpx2` error, and a keepalive error frame has no status on its object: `_frame_status` reads it from the body. The mixins already know the status when they build the error.
- **Parse the status from the message.** The message is built for people and can hold the body of the reply. A parse is the hand-rolled code that AGENTS.md rules out.
- **A structured (JSON) log.** The Service writes plain text. The issue does not ask for a new format.
- **Add the reason to `RoadmapRefineError` and the record.** The issue asks for the warnings. The error and the record keep their text, so they cannot gain model text.
