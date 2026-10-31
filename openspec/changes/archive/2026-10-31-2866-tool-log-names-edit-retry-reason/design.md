# Design

## Decisions

- **Read the reason from the error that the hook already gets.** `ToolCallLog._execute` catches `ToolRetryError` and `UnexpectedModelBehavior`. The first has the `RetryPromptPart`. The second has the `ModelRetry` in `__cause__`. One loop over the cause chain finds the text of either. The text is a string only for a `ModelRetry`. A list of validation errors gives no reason.
- **No reason for a refusal by policy.** A `PermissionError` in the cause chain means a shell refusal or a path outside the root or a protected path. The text of a shell refusal repeats the command, and the text of a path refusal names an absolute path that the model chose. The spec of the line already keeps both out. The line says `retry` or `refused` as before.
- **Show the path only when the reason lacks it.** The messages of `edit_file` name the path. Some do not, such as the missing pair of `old_text` and `new_text`. In that case the line appends the `path` argument as `Path: <path>`, so a long path cuts only the end of the reason. The text is built once, then masked, escaped and cut, so the path has the same limits.
- **Mask first, escape, then cut.** `bounded_text` masks and cuts to a read limit, so a cut cannot split a secret. The escape with `unicode_escape` makes one line. The last cut to `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS` fixes the length, and a cut text ends with ` ...` as the command does.
- **Keep the last three reasons of each tool.** A `deque` with `maxlen` is the bound. The stop reason lists the reasons of the tool that exceeded its retries, which is the tool of the call that raised `UnexpectedModelBehavior` in the hook. The code does not parse the message `Tool 'x' exceeded max retries`.
- **Same text in the log and in the comment.** The log line and the stop reason use the stored bounded text, so the comment shows no more than the log.

## Rejected alternatives

- **Read the next request of the model for the `RetryPromptPart`.** It sees the same text one turn later and needs a second hook. The hook that runs the tool already has the error.
- **Match the text `old_text not found` to name a cause.** It reads the text of a library and breaks on a new release. The message is shown as it is.
- **Show an excerpt of `old_text`.** It is file content or model text, and the stop comment is public. The cause is clear without it.
- **Log the validation errors.** Their `input` field holds the arguments of the model, and a message of the validator can echo them.
- **Raise the log limit to the whole message.** A message can hold a long path or pattern. A constant length keeps the Job log small.
