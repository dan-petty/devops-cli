# Proposal

## Why

Issue #3065 (tracker #3027): a stop of the implement job is one comment with the last error. The recovery differs by cause: a provider error needs a retry, a parser bug needs another model tier, a failing test needs a fix step, a wrong plan needs an amend, a false premise needs a return, a process killed for memory needs a higher limit. Today a person reads each stop and decides. The Service cannot count the stops by cause either, so a cause that repeats does not show.

## What Changes

- A new module `src/devops_cli/roadmap/failure.py` holds the taxonomy. `classify_failure` is a pure function: it reads the error text, the exit status, the refusal of a tool, the name of the check and the last message of the agent, and returns one of 12 classes (`provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `conflict`, `ci_infra`). Input that no rule matches is `ci_infra`.
- `ACTION_BY_CLASS` is the one table of defaults, with one action for each class: `retry`, `change_tier`, `repair`, `amend`, `return`, `raise_limit` or `wait`.
- The stop comment of the runner names the class, the action taken and the action left. The job has taken `repair` when it ran fix rounds before the stop. The action left is the default of the class, or `wait` when that default was taken already.
- The runner records the class in the new key `implement.failure` with `implement.stopped`, and writes one line with the class and the action left to the Job log, which is the trace of the Job. A retry and a clear of the Service remove the key with the stop.
- The Service counts. When a round reports a Job that left a stop, it adds 1 to the counter `devops_cli_service_implement_failures_total` with the label `class`. For a Job that left the item without a result, the round classifies the tail of the log of the Job, records the class with the stop, and names the class and the action left in the report.
- The table test of the classifier uses the stop texts of #2175, #2735 and #2747 and the failed-test text of #2924, and the messages that the job writes for each other class.
- The change adds behavior that a consumer sees (a comment, a record key and a metric), so it carries spec deltas.
- The change fits one pull request.

The change does not run any action by itself. See the design and Feasibility. The action table says what remains for the item; a person or a later issue runs it.

## Capabilities

### New Capabilities

- `roadmap-failure-taxonomy`: the classes, the classifier and the one table of default actions.

### Modified Capabilities

- `roadmap-implement-job`: the stop comment, the job record, the trace and the metric name the class (added requirements; no existing requirement changes).

## Impact

- Code: `src/devops_cli/roadmap/failure.py` (new), `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md` (the `/metrics` list), `openspec/specs/roadmap-failure-taxonomy/spec.md` and `openspec/specs/roadmap-implement-job/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_failure.py` (new), `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_job_scoped.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_stop_clear.py`.

## Feasibility

- The stop texts exist. The stop comments of #2175 (comment of 2026-11-01 10:46), #2735 (2026-10-31 13:02) and #2747 (2026-10-31 19:47) hold a `mypy --strict` failure, `Tool 'edit_file' exceeded max retries count of 5` and `ModelHTTPError: HTTP 400 ... Ollama_chatException`. #2924 is a pull request with no stop; its review notes hold "10 tests failed on the base and pass now", the one failure text in it. The table test uses these texts as they are, read with `gh api repos/dan-petty/devops-cli/issues/<n>/comments`.
- The premise "the implement job takes the action of the class" cannot be built today, and the change does not build it. `git grep -n -i tier gh/main -- src/devops_cli/roadmap` prints nothing, so the job has no model tier to change. The runner Job takes its memory limit (8 Gi) from the CronJob template `k8s/devops/cronjob-runner.yaml`, which Image Updater and a person own; the Service has no write to it (its Role creates and reads Jobs, lists pods and reads pod logs only). A retry exists only as the comment `implement: retry` of a person and the clear rules of `stop_clear.py`. The one action that the job runs is the fix round (`roadmap.implement.repair_rounds`, #3043). So the change records the class and the default action, and shows both, and the dispatch of the other actions stays a person's step. The issues that own the other actions are named under Workflow follow-up in `tasks.md`.
- The metric cannot be counted in the runner. The runner pod ends after the Job and no Prometheus job scrapes it; the Service exports `/metrics` (`k8s/monitoring/prometheus-values.yaml`). So the Service counts when a round reports the Job.
- The Service cannot see why a pod was killed: `ClusterJobs.log_tail` reads the log only, and `ClusterJob` holds the condition (Complete or Failed) only. A pod killed for memory leaves no line in its log, so such a Job is `ci_infra` until the Job API reads the state of the pod. A command of the runner that the kernel kills exits with status 137 and is `oom`.
- The classifier was run on the excerpts above with `uv run devops ci test tests/roadmap/test_roadmap_failure.py`: 43 cases pass.

## Existing Tool Considered

No open, maintained library classifies the failures of this job: the classes name the stop reasons of this job (`plan_defect`, `refused_tool`) and its actions. A general log classifier or an error-tracking service (for example Sentry grouping) groups by stack trace and cannot say `amend` or `return` for a roadmap item, and it needs a network egress that the Job does not have. The change builds a table of regular expressions and a table of actions. Written cost: about 60 000 tokens to build the module, the wiring and the tests; about 3 000 tokens a month to keep it, as a new stop text needs a rule; about 15 000 tokens to fix the rules when a real stop is misclassified; about one working day. The change deletes no code.
