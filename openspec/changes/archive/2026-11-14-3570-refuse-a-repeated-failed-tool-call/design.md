# Design

## Decisions

**The digest is `argument_digest`, which the trace already computes.** It hashes the tool name and the normalized arguments, so a changed argument has another digest, and the log has one digest of a call for its line and its trace.

**The set holds the first reason of each digest.** A later failure of the same call adds no second reason, and the model reads the reason of the call that failed first. `setdefault` keeps the first and needs no order.

**The refusal is a tool result, not a raised error.** The model reads the earlier reason as the result of the call and takes another step, as the issue asks. A raised `ModelRetry` would use one of the tool's retries, and a repair round that repeats a call would end sooner than a round that tries a new call.

**A successful call is not recorded.** The same read twice is a normal step, and the guard is about a failed action.

**The reason is the masked text of `logged_reason`.** A path outside the checkout is already `<path>`, so the refusal cannot show what the log hid.

## Rejected alternatives

- **A set of failed tool names.** A changed argument is a new attempt, and the rule refuses only an unchanged repeat.
- **A `ModelRetry` with the refusal.** It spends a retry of the tool and ends a run that the model could have repaired.
- **A new executor hook.** `_execute` is the one place that sees every call and already computes the digest.
