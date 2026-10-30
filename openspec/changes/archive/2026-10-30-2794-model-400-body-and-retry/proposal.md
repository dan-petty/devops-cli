# Proposal

## Why

Issue #2794. The implement Job for #2656 stopped at group 1 with the reason `ModelHTTPError: HTTP 400, model devops-coder`. The reason does not say why the gateway answered 400. The cause was only in the log of the gateway pod: Ollama could not read a tool call of the model (`XML syntax error on line 75: unexpected EOF`). The step discarded its work for one bad sample of the model.

## What Changes

- The reason of a step that a failed model call ended holds the error text of the body of a `ModelHTTPError`, after the status and the model. The step takes only a string from the body (the body itself when it is a string, else its `message`, else its `error`). It masks the text with `mask_secrets` and cuts it to `CONST_ROADMAP_RUN_ERROR_CHARS` characters (`bounded_text`). A provider can echo the output of the model in its error text (Ollama writes `raw='...'`), and the masker finds a secret only by its form. So the step also keeps only the first line, hides quoted text, and stops at the first `=` or `;`, as `run_error_message` does for other errors (#2562). No other value of the body goes in the reason.
- `_run_agent` sends the request again when the answer is an error that the provider reported inside an open stream, with the status 400 (`in_stream` is set, and the error is not a context window error). The history is the same: the step drops the interrupted reply of the failed request and resumes the conversation with the request that was pending. The step resends one failed request at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times in a row, which is 1. A send that gets a reply gives the next failed request its own resend, so two separate failures in one turn do not use up one budget. After the last try, the step stops with the body of the answer. The resend adds to the retries of the client (`ai.max_retries: 1`, #2500). The client retries only 5xx, 429 and connection errors, and the resend only this 400. So one call gets at most (1 + `ai.max_retries`) * (1 + `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS`) sends, which is 4.
- The failed request counts in the spend and in the request limit of the step. The resumed conversation carries the usage of the replies that came before and one request for the failed send. So the model gets no more requests than `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS`.
- No manifest changes. No output limit cuts the call (see Feasibility).
- A consumer observes the reason and the number of model requests, so the change carries a spec delta. It renames and modifies one requirement of `roadmap-implement-step` and adds one.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the reason of a failed model call holds the error text of the body. A new requirement says that an error inside an open stream with the status 400 is sent again.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_roadmap_implement_step.py`, `tests/support/model_script.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

All facts below are from 2026-10-30, from the cluster (read-only), the Loki datasource of Grafana, and the library source of pydantic-ai 2.59.0 (the version in `uv.lock`).

- The error was inside an open stream. The log of the gateway pod shows the failure in `litellm/litellm_core_utils/streaming_handler.py` (`__anext__`, `_handle_stream_fallback_error`), called from `async_data_generator`. The HTTP status 200 was sent before. pydantic-ai maps an error object inside a stream of an OpenAI-compatible API with `_model_errors.stream_error`: the error gets the status from the `code` of the body (`"400"`), and `in_stream` is set. So the reason `HTTP 400` of #2656 is that mapping. A request that the provider refuses before it streams has `in_stream` false.
- No output limit cut the call. Loki holds the log of the pod `ollama-48gib` (the pod behind the route `devops-coder`). At 18:42:32 UTC it logged `qwen tool call parsing failed error="XML syntax error on line 75: unexpected EOF"` (`source=qwen3coder.go:87`), which is the parser of Ollama. The slot log of the same request says `n_ctx_slot = 128000`, `task.n_tokens = 21933`, and `stop processing: n_tokens = 22828, truncated = 0`. So the model made 895 tokens in 12.3 s, in a window of 128000 tokens, and nothing was truncated. The route `devops-coder` in `k8s/llm/gateway/config.yaml` sets no `max_tokens` and no `num_predict`. `ollama show qwen3-coder:30b --parameters` lists `temperature`, `top_k`, `top_p`, `repeat_penalty` and three `stop` strings, and no `num_predict`. `ai.max_tokens` has the default `None`, and the Ollama default for `num_predict` is unlimited. So the model ended its own reply inside the XML of a tool call (a sample at the temperature 0.7), and the next sample can be whole.
- pydantic-ai does not send the request again. The OpenAI SDK retries a connection error, 408, 409, 429 and 5xx, and not a 400. `on_model_request_error` can recover a failed request, but the source says "`on_model_request_error` cannot recover an error after streaming has begun" (`pydantic_ai/_agent_graph.py`). The run streams because the step has an event stream handler (#2379), so the hook does not fire for this error. `ModelRetry` is no choice: it adds a retry prompt to the history and counts against the retry budget of the tools. So the resend belongs around the run.
- The resume works. A faked run with a stream that yields a text and then raises `ModelHTTPError(400, ..., in_stream=True)` leaves the messages `[request, reply, request, interrupted reply]`. Run with `conversation=Conversation(messages=<without the interrupted reply>)` and no prompt, the next request of the model sees `[request, reply, request]`, the same history as the failed one.
- The rule of #2500 ("each model call in the cluster is sent at most two times") sets `ai.max_retries: 1` of the roadmap service for the retries of the client. The resend of this change is a second layer on top of it, so the bound of #2500 does not hold for one call: the real bound is (1 + `ai.max_retries`) * (1 + `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS`) sends. It is acceptable, for the two layers retry different errors and the request limit of the step bounds all sends.

## Existing Tool Considered

pydantic-ai gives the resume (`Conversation`, a run with no prompt), the usage (`RunUsage`) and the error (`ModelHTTPError.in_stream`, `.status_code`, `.body`). `bounded_text` masks and cuts the body. No library retries an error inside a stream (see Feasibility). The change builds only the loop of one resend and the choice of the text of the body. Estimated cost of what it builds: about 60 lines of code, 120 lines of tests, about 100k tokens of agent work, and two hours of elapsed time. The upkeep is small: the code uses the public API of pydantic-ai.

The change deletes no code. It replaces the sentence in `_model_call_reason` that kept the body out.
