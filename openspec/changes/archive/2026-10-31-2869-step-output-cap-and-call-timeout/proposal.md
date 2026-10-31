# Proposal

## Why

Issue #2869. The implement Job for #2739 stopped at group 1 after 27 minutes with `ModelServerError: HTTP 500, ... Timeout on reading data from socket`. One model call ran for 25 minutes. The model never stopped: it made 57,653 tokens, and the gateway ended the call at its timeout of 1500 seconds. The tier has `OLLAMA_NUM_PARALLEL=1`, so the runaway call held the only slot, and the next request to the tier waited behind it for about 20 minutes.

Nothing in the chain caps one reply. The agent of a step sets no `max_tokens` and no deadline, and the route `devops-coder` sets none.

## What Changes

- The agent of a step gets model settings from two constants in `config/constants.py`. `CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS` is 16384 and is the `max_tokens` setting. `CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS` is 600 and is the `request_timeout` setting. Pydantic AI enforces `request_timeout` as one deadline over the whole request: every attempt of the client, and the read of the stream to its last chunk. The `timeout` setting would not do this, because on a stream it limits only the wait for each chunk, and a runaway model sends a chunk every few milliseconds.
- A reply that ends with the finish reason `length` stops the step at once. A hook of the agent (`after_model_request`) reads the finish reason that the library reports, and raises `OutputCapReached`. Its message names the cap and its value, and it is the reason of the stop. The step matches no text. The hook is needed because Pydantic AI does not stop on that reply: a tool call that the cap cut still runs, and `write_file` of the harness wrote the broken arguments as the content of a file (see Feasibility).
- A call that runs past the deadline stops the step. The reason of a `ModelRequestTimeout` names the deadline in seconds.
- The issue text says that the existing resend takes over after a runaway call. This change differs on purpose. A resend would repeat a call that costs up to 600 seconds, so these two stops get no resend. Neither stop is sent again. The resend of #2794 covers only a 400 inside a stream. A `ModelRequestTimeout` and `OutputCapReached` are no such error. A cap that cuts a tool call can reach Ollama as a parse error, which is such a 400. The resend is then bounded by `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS`, so a capped call takes at most (1 + that value) times the deadline.
- The instructions of the step tell the model that a reply has an output cap, and to write a long file in parts with `edit_file`.
- The gateway does not change (see Feasibility).
- A consumer observes the reason and the model settings, so the change carries a spec delta. It adds two requirements and modifies one of `roadmap-implement-step`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: a model reply has an output cap and a call has a deadline. A reply that reaches the cap, and a call that runs past the deadline, stop the step with their cause.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_output_cap.py`, `src/devops_cli/exceptions/ai_pydantic.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `tests/roadmap/test_roadmap_implement_step_output_cap.py` and the test of the instructions.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

All facts are from 2026-10-31. They come from the cluster (read-only), the pinned library source, and the Job logs.

- **The runaway.** The log of the pod `ollama-48gib-gb2m4` shows the slot task 1542: `new prompt, n_ctx_slot = 262144, task.n_tokens = 31063`, 29,200 tokens from the prompt cache. The slot log prints `n_gen = 57653` at 13:37:35, at 63 tokens per second at first and 38 at the end. The `[GIN]` line is `200 | 25m0s | POST /api/chat`. 25 minutes is `router_settings.timeout: 1500` of `k8s/llm/gateway/config.yaml`. The call was a streamed call that made tokens all the time, so a read timeout of the HTTP client would never have fired.
- **The second long line is not a second runaway.** The line `22m0s` at 13:38:56 is a request with a prompt of 3,502 tokens. It waited behind task 1542 and ran for 47 seconds, with 1,226 tokens, after the slot was free. The step sent one request: its 500 is no 400 inside a stream, so the resend of #2794 did not apply, and the Job log has no second send. The cost of the runaway is the slot that it held.
- **The cap reaches Ollama.** Pydantic AI 2.59.0 sends `max_tokens` to an OpenAI chat model as `max_completion_tokens` (`pydantic_ai/models/openai.py`, `openai_chat_supports_max_completion_tokens` is true by default). The pinned LiteLLM of the gateway (v1.103.0, read in the pod) maps both `max_tokens` and `max_completion_tokens` to `num_predict` for `ollama_chat` (`litellm/llms/ollama/chat/transformation.py`). Running `OllamaChatConfig().map_openai_params({'max_completion_tokens': 16384}, ...)` in the pod returns `{'num_predict': 16384}`. The stream maps `done_reason` through `map_finish_reason`, and `map_finish_reason('length')` returns `length`. `ai.max_tokens` does not do this job: only the Ollama path of `pydantic_ai_bridge.py` reads it, and the gateway path does not.
- **The library ends the call at the deadline, and reports the cap in the reply.** `ModelSettings['request_timeout']` is "a deadline for one request to one model, in seconds, enforced by Pydantic AI for every model", and it raises `ModelRequestTimeout`. A reply that the cap cuts has `finish_reason == 'length'`. Pydantic AI does not stop on it. A cut text ends the run as its output. `IncompleteToolCall` (`_agent_graph.py`, `check_incomplete_tool_call`) is raised only when the arguments of a cut call fail validation past the retries of the tool. A test with a fake server that obeys the cap showed the rest: the harness accepted the broken arguments of a cut `write_file` call (`{"INVALID_JSON": ...}`) and wrote them as a file, and the run went on to the next request. So the step needs its own stop at the first cut reply.
- **The longest honest reply.** The slot logs give `eval time = ... ms / N tokens` for each finished reply. In the windows of the three Jobs of 2026-10-31 on `ollama-48gib` (75 replies) the longest reply is 1,881 tokens. In the Loki log, the windows of two Jobs of 2026-10-30 give 1,059 and 1,595. So the longest honest reply of a step is under 2,000 tokens. The longest reply of any client on the tier in the 14 hours of the pod log is 11,634 tokens (a review). The largest module of the project, `implement_step.py`, is 12,307 tokens, and the largest test file of the roadmap domain is 18,461 tokens. A cap of 16,384 tokens is 8 times the longest honest reply of a step, and above the longest reply of any client. A file bigger than the cap is written in parts with `edit_file`.
- **The deadline.** The prefill of the tier runs at about 1,500 tokens per second (the longest prompt in the log, about 119,000 tokens, took 78 s). The input of a step is at most 128,000 tokens, so a prefill with a cold cache takes about 90 s. A reply at the cap, at the average rate of the longest call (38 tokens per second at a context of 88,000 tokens, the `tg` value of task 1542), takes 16384 / 38 = 431 s. The sum is 520 s, and the deadline is 600 s. That is 40 percent of the gateway timeout. In the same log line the rate of a 3-second window fell to 27.55 tokens per second. At that rate a reply at the cap takes 595 s, and with the prefill 685 s, which is more than the deadline. So a very slow call ends at the deadline before it reaches the cap. Early in the same task the rate is 53 tokens per second, so the cap normally comes first. Both stops end the step with their cause, and a runaway call ends in 4 to 10 minutes.
- **The gateway.** No change. The code path covers the client: `DEFAULT_AI_IMPLEMENT_MODEL` is the only default that names `devops-coder`, so the implement step is the only client of the route in the repository. Reviews have their own routes. A cap in `litellm_params` of the route would also cap `devops-reasoning`, which falls back to `devops-coder`, with a number that belongs to the step. The cap would also be a second copy of a number that a constant holds.

## Existing Tool Considered

Pydantic AI covers the need: `ModelSettings['max_tokens']` and `ModelSettings['request_timeout']`, the `finish_reason` of a `ModelResponse`, the `after_model_request` hook and `ModelRequestTimeout`. LiteLLM maps the cap to `num_predict`. The change builds only the two constants, the reason text, and a hook of about 15 lines that raises on the finish reason `length`. Estimated cost: about 40 lines of code, 150 lines of tests, about 80k tokens of agent work, and two hours of elapsed time. The upkeep is small: the code uses public settings and fields of Pydantic AI.

The change deletes no code.
