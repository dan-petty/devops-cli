# Proposal

## Why

A Job of the implement job can end with no result: a pod that the kernel killed or evicted, a Job that the Service ended by its stall, or a Job that no longer exists. Then the round sets the item Blocked and records `implement.stopped` as `job`. Only a comment `implement: retry` of a person, or a new runner image, clears that stop (`stop_clear.py`). So one lost Job stops the item until a person looks at it (#3721).

This is the continuation part of #3062. The liveness signal (#3063) and the checkpoint of each task (#3054) exist. The checkpoint of each passed group needs an owner decision and stays in #3062.

## What Changes

- A new clear rule `continue` in `stop_clear.py`. It applies to `implement.stopped` as `job` when the class in `implement.failure` has the action `retry` in `ACTION_BY_CLASS`. It runs before the rule `digest`, reads no template and spends no clear by digest.
- A new setting `roadmap.implement.continuations_per_item`. The default is 2, and 0 turns the rule off. The variable is `DEVOPS_CLI_ROADMAP_IMPLEMENT_CONTINUATIONS_PER_ITEM`.
- A new record key `implement.continuations`. It holds a count and no other data, so it holds no secret. It stays after a clear.
- The comment of a continuation says "continuation n of N". At the limit it also says "No continuation is left". Then the item stays Blocked until a comment `implement: retry`, as before.
- The class `DigestLimits` becomes `ClearLimits` and holds the third limit. The old name goes away. No shim stays.
- The report of a Job with no result (`implement_job_report_stopped`) says what the Service does next.
- The new Job takes the branch from `origin`. So the work that a push put there continues: the `wip:` commits of a group with more than one task (#3054). A group of one task that passed, and that no push kept, runs again until the checkpoint of each group exists (#3062).
- The 13 tests of `test_roadmap_implement_submit.py` and the 2 tests of `test_roadmap_implement_deadline.py` that read the stop of a failed Job use the fixture `no_continuation`, which sets the limit to 0. New round tests cover continuation 1, continuation 2 and the Blocked item.
- A consumer observes the rule, the setting, the record and the messages, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The Service continues a Job that ended without a result. The stop of a Job and the rule `digest` hold when no continuation applies.

## Impact

- Code: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/test_roadmap_digest_clears.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/test_roadmap_implement_project_steps.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_implement_deadline.py`, `tests/security/test_config_declarations.py`, `tests/support/roadmap_implement.py`
- Documents: `k8s/README.md` (Roadmap service, step 16), `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `docs/ROUTINE_TASKS.md`, `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` (generated)

## Feasibility

Checked against `origin/main` at `60eb89ed`.

- `git grep -n "continuations" origin/main -- src tests docs k8s` prints nothing, so no continuation exists. `stop_clear.py` holds the rules `retry` and `digest` only. The open pull requests (#3628, #3641, #3657, #3668, #3714, #3718) change none of `stop_clear.py`, `implement_submit.py` and `implement_deadline.py`. #3714 changes `store.py`, `messages.py` and `k8s/README.md`, and #3718 changes `docs/ROADMAP_WORKFLOW.md`, so the branch is rebased before the first push.
- `_report` in `implement_submit.py` sets Blocked and records `implement.stopped` as `job` with the class of the log (`classify_failure`). A Job that the Service ended by its stall gets the exit status 143, which is the class `timeout`. A log with no sign of a cause is `ci_infra`. A log with an out-of-memory kill is `oom`. `ACTION_BY_CLASS` gives `retry` to `provider`, `timeout`, `ci_infra` and `head_moved`, and `raise_limit` to `oom`. So a kill with no sign in the log and a stall continue, and a kill that the log shows as out of memory waits for a person.
- `k8s/devops/cronjob-runner.yaml` sets `backoffLimit: 0` and `activeDeadlineSeconds: 7200`. The Kubernetes documentation of Jobs (https://kubernetes.io/docs/concepts/workloads/controllers/job/, read on 2026-11-06) says: "a Job's `.spec.activeDeadlineSeconds` takes precedence over its `.spec.backoffLimit`", and "there is no automatic Job restart once the Job status is `type: Failed`". So the Job controller cannot continue the run, and a continuation is a new Job from the Service.
- `_groups` in `implement_run.py` records a passed group with `_record` and does not push it. `_keep` pushes a `wip:` commit only while tasks of the group are unticked (#3054). So the new Job continues the work of a group with many tasks, and a passed group of one task that no push kept runs again. The evidence comment on #3062 shows this with a replay test. The checkpoint of each group conflicts with #2910, #3043 and the false-premise return, and stays in #3062.
- A draft of this change ran in an earlier worktree on a base that was 34 commits older. It was ported by hand to this base: `stop_clear.py` and the tests apply, and the docstring and the messages were corrected where the base changed.

## Existing Tool Considered

- Kubernetes Job controller: `backoffLimit` restarts a pod inside one Job, and the documentation above shows that a deadline ends it and a Failed Job is never restarted. The template sets `backoffLimit: 0` on purpose, so a pod that restarts would hide a stall from the report.
- Argo Workflows `retryStrategy`: it re-runs a step and keeps no checkpoint. The runner is not on Argo (#1535 steps 2 to 6 are not built).
- Temporal: rejected by ADR 0008. It needs a new Postgres and 3 to 6 pods. The liveness signal and the `wip:` push exist.

No open tool starts a new Job for an item from a GitHub record. The change reuses `clear_stops`, `ACTION_BY_CLASS`, `write_each`, the job record and the settings model, and the pydantic `TypeAdapter` for the count. It adds no dependency. To build it costs about 120k tokens (the draft and this port), about 3k tokens a month to keep, and about 10k tokens to fix when the class table changes. The elapsed time is about 4 hours. The change deletes the name `DigestLimits`.
