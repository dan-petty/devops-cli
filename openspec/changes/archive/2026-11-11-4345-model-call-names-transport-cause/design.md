# Design

## Decisions

- **Read the phase from pydantic-ai.** `ModelConnectionError.phase` gives the stage of the request (`pool`, `connect`, `write`, `read`). pydantic-ai finds it from the chain of the transport error, so the change does not read the chain for the phase again.
- **Name the first error of the cause chain.** The chain of a failed call through the OpenAI client is `ModelConnectionError` from `openai.APIConnectionError` from the `httpx2` error. The message of the SDK error is only `Connection error.`, so the change names the class and the text of the first error, where the HTTP library states what broke. The walk stops at an error that it saw before, as `transport_phase` of pydantic-ai does.
- **Mask and cut the text.** The text goes through `bounded_text`, as the other stop text of a run does. A transport error holds no text of a model reply.
- **The message is the check for the cause.** The cause is outside the project, and the logs do not confirm which part of the path broke (proposal, Feasibility). No offline test can reproduce a cause that is not known. The stored report of `devops roadmap eval verify` keeps the message of each failed case, so when the failure returns, its report names the phase and the transport error, and the tests of this change fail if the message loses them.
- **Keep every other message.** A failed call with an HTTP status, and a transport error with no cause, keep the message that they have now. The `status` and the `timed_out` of the `AIClientError` do not change.

## Rejected alternatives

- **Retry a failed model call.** The issue and AGENTS.md forbid a retry that hides a cause outside the project. The OpenAI SDK already retries a request that gets no response two times.
- **Log the cause at each caller.** The investigation and the implement step both call `model_call_error`. One change there serves both, and the report of the eval holds the message, not a log line.
- **Test a second event loop.** The traces show that every case of a process ran on one worker thread and so on one event loop. A test of a second loop would guard a mechanism that did not cause these failures.
- **A test against a fake gateway that drops the connection.** The OpenAI SDK sleeps between its retries, so the test would take seconds. The test builds the same chain of errors that pydantic-ai raises and runs it through the investigation.
