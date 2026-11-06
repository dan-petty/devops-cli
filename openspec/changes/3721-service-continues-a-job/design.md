# Design

## Decisions

- **The continuation is a clear rule in `stop_clear.py`, and it adds no job and no lane.**: The pass already lists the comments, reads the issue again before it writes, writes the Status with the marks, and comments after the write. The rule `continue` uses all of that. The same round makes the new Job, because a cleared item is eligible in the round that clears it.
- **The rule applies to `implement.stopped` as `job` only.**: That value is the stop that the runner could not write, so the run left no result. A stop that the runner wrote has a step name, a class that the step chose and its own rules (#3065).
- **The class gate is `ACTION_BY_CLASS`, with the action `retry`.**: One table decides for the rule `digest` and for the rule `continue`. A stall gives `timeout`, a log with no sign gives `ci_infra`, and both continue. A log with an out-of-memory kill gives `oom` with `raise_limit`, and a second run on the same limit ends the same way, so it waits for a person. A stop with no class on record waits for a person.
- **`implement.continuations` holds a count as text, and `TypeAdapter(NonNegativeInt)` reads it.**: The record is a map of text. The adapter refuses `two`, `-1` and `1.5` with the same message form as the settings, so the rule needs no hand-written parser. A count that does not parse stops the rule for that item, with a warning, and a comment `implement: retry` still clears the stop.
- **The count stays after a clear, and a retry of a person does not reset it.**: The limit is for one item, as the limits of the rule `digest` are (#3481). A reset would add a write to the retry path and a second state to read. A person who wants more runs comments `implement: retry` for each run.
- **The rule runs before the rule `digest`.**: A Job that ended with no result on a new image would otherwise spend a digest clear, and the digest budget would run out on transient failures. `_rule` reads no template for a continuation.
- **`ClearLimits` replaces `DigestLimits`.**: The pass reads three limits from the settings, so one tuple holds them. The project is alpha, so the old name goes away and no alias stays.
- **The comment says "continuation n of N", and "No continuation is left" at the limit.**: The person who reads the item sees how many runs the Service spent, and when it stops.
- **The new Job takes the branch from `origin`, and the change adds no code for that.**: `_worktree` in `implement_run.py` already takes the branch from `origin` with its `wip:` commits (#3054). The change does not push a passed group.
- **The tests that read the stop of a failed Job use a fixture, `no_continuation`.**: The fixture sets the limit to 0 with the shared `config` fixture, in `tests/support/roadmap_implement.py`. The round tests of the continuation use the default.
- **The default is 2.**: A kill, an eviction or a stall costs at most two more runs of about an hour each. A third run on the same item points to a cause that a person must look at.

## Rejected alternatives

- **Kubernetes `backoffLimit` above 0, or a `podFailurePolicy`.**: The documentation says that a Job's `activeDeadlineSeconds` takes precedence over its `backoffLimit`, and that a Failed Job is never restarted. A stall ends a Job by its deadline, so the controller could not continue that case. A new pod inside the same Job also keeps the Job running, so the Service would report it later and see no stop.
- **Argo Workflows `retryStrategy`.**: It re-runs a step with no checkpoint. The runner is not on Argo yet (#1535).
- **Temporal.**: ADR 0008 rejects it. It needs a new Postgres and 3 to 6 pods, and the checkpoint and the liveness signal already exist in git and in #3063.
- **A heartbeat field in the job record.**: #3063 rejected it. It costs one GitHub write for each tool call.
- **A push of each passed group, to make the continuation exact.**: It conflicts with #2910 (a claim pushes nothing), #3043 (the scoped-check stops push nothing) and the false-premise return. It needs an owner decision and stays in #3062.
- **A new failure class such as `lost_job`.**: The class list is fixed (`failure.py`), and the log of a lost Job has no sign of its own.
- **Count the continuations in `implement.digest_clears`.**: It would spend the digest budget, which the issue forbids, and the entries hold a digest that a continuation does not have.
- **Reset the count when a person comments `implement: retry`.**: See the decision above.
