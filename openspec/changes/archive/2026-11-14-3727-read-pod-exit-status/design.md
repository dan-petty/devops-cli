# Design

## Context

`_report` in `src/devops_cli/roadmap/implement/implement_submit.py` reads the tail of the log of the Job's pod and calls `classify_failure` with the log. `FailureEvidence` already holds an `exit_status`, which only the stall path sets to 143. `classify_failure` maps 137 to `oom`.

## Goals

- Read the exit status of the terminated container of the pod whose log the report reads.
- Keep 143 for a stall.

## Decisions

- **Read `state` then `lastState`.** A restarted container keeps the termination in `lastState` while `state` is running or waiting.
- **The first pod, as the log does.** `log_tail` reads the first pod of the Job label, so the exit status comes from the same pod.
- **A read failure is no status.** The report catches `ClusterJobError` and passes None, as it does for the log, so a report never waits for a status that is not there.

## Risks

- A pod with several containers takes the first terminated status. A runner pod holds one container, and the log read takes the same pod without a container name.

## Tests

- A pod with `OOMKilled` and exit 137, and an empty log, gives `oom`, stops the item, and makes no continuation Job.
- A restarted container whose `lastState` holds 137 gives `oom`.
- A pod with no terminated state keeps the class of the log.
