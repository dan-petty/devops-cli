# Design

## Decisions

- Find a retry with `is_retry(part)`, which pydantic-ai 2.69 gives for this check. A retried `ToolReturnPart` stays out of the tool answers of the trace and out of the match lines of a search tool, as a `RetryPromptPart` did.
- Keep the stock `Coder` of 0.71. The new instructions, the strict default and the answer to spent retries come with the upgrade. The next items of #6519 run `Coder` as upstream runs it, so the change writes no code to undo them.
- Record the retry parts from a run of an agent on the installed pydantic-ai, and replace only the content of the part when a test needs given errors. A part that the framework no longer builds then fails the test.
- Read an error frame of the stream before the class of its error: pydantic-ai 2.71 gives the 408 frame the category `ModelTimeoutError`, and the frame is not a timeout of the client.
- Catch `ToolFailed` in `ToolCallLog._execute`: pydantic-ai 2.71 turns it into `ToolFailedError` only after the hooks that wrap the tool return, so the log saw neither error for the call that `Coder` answers.
- Match `Model\w*Error: HTTP <status>` in the provider rule: the reason of a failed model call names the class and the status, and every class of an HTTP error of pydantic-ai is a `ModelHTTPError`. A transport timeout, which has no status, keeps its class.
- Test the last-retries line of `ToolCallLog` on an agent with no `Coder`, where a tool still ends the run when it spends its retries.

## Rejected alternatives

- Keep the `RetryPromptPart` checks: pydantic-ai 2.71 builds no such part, so 4 tests of the stage toolbox found 0 violations where the run had 1.
- Strip the spent-retries answer of `Coder` in `_tune`: it is a private class of the harness (`_ReportExhaustedRetries`), and the next item of #6519 adopts the stock `Coder`.
- Keep `pydantic_ai_harness.filesystem`: it gives a `HarnessDeprecationWarning` on 0.71.
