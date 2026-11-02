# Design

## Decisions

- **The Service moves the deadline.** The Service already creates the Job, lists the Jobs of the repository in each round and reads the log of a Job's pod. The runner pod has no Kubernetes token (a policy and a test hold it), so it cannot extend its own deadline. A patch of `activeDeadlineSeconds` is allowed by the API server on a running Job (see Feasibility in the proposal).
- **The state lives on the Job.** The digest of the last log tail and the time of the last progress are annotations of the Job (`roadmap.devops-cli/progress`, `roadmap.devops-cli/progress-at`). The API is the store, as it is the lock for the Job: a restart of the Service loses nothing, and no second record is needed. A Job without `progress-at` is not a Job of the Service and is left alone. A Job that a person starts with `devops k8s run-job` keeps its template deadline.
- **Progress is a changed log tail.** The runner writes one line for each tool call to the Job log, and a Job that is silent writes none. The Service compares the digest of the last 20 lines with the digest it stored. A log that is empty gives no signal. This needs no runner change and no GitHub write. A tool call that retries forever also changes the log; the ceiling and the tool-call limit of a step bound it.
- **The deadline follows the work.** After a progress event the deadline is `max(deadline in force, seconds since the start + extension)`, cut to the ceiling. It never goes down on progress. The extension is the backstop for a Service that is down: the Job ends at most one extension after its last seen progress.
- **The Service ends a stall, not the deadline.** A stall is `deadline_stall_seconds` of unchanged log seen by the Service. The Service then patches the deadline to the seconds since the start. The Job ends by its deadline with the reason `DeadlineExceeded`, which is what the issue asks for, and the report names the stall. If the extension were below the stall, the deadline would pass before the Service saw the stall, so the validator refuses it.
- **The defaults come from the silent waits of the runner.** The longest silent wait is the watch of the checks (1800 s). The stall is 2400 s. The extension is 3600 s, the stall plus the 571 s that a row can be late. A test computes both bounds from the constants, so a longer wait in the runner fails the test and does not kill a run in production.
- **The ceiling has a cap in the policy.** The policy `roadmap-service-jobs` allows 14400 s. The setting `deadline_ceiling_seconds` has the same maximum, held by a test. A person who needs more changes both in one pull request.
- **The trace is a span.** Each extension and each stall is a span `implement.deadline` under the span of the round. It carries the Job, the old and the new deadline and the reason. The Service already sends the spans of its rounds, so no new exporter is needed.

## Rejected alternatives

- **A sidecar or a controller that extends the deadline.** A sidecar would need the Kubernetes token that the pod must not have. A controller is one more deployment for one Job type.
- **A heartbeat written by the runner to the item record.** One GitHub write for each tool call, against the hourly budget of the Service (`service.github_requests_per_hour`). The log line exists already.
- **A stall of 300 s, as the issue proposes.** The runner is silent for up to 1800 s in a normal wait (see Feasibility), so 300 s ends healthy runs.
- **Add the extension to the deadline in force on each event.** With a row every 7 minutes and an extension of an hour, the deadline would reach the ceiling after a few events and say nothing about the work. The deadline anchored to the time since the start stays near the work.
- **Tiers of memory and CPU by the number of files.** Out of scope: see the proposal.
