# Proposal

## Why

No metric shows what happens to an item after the implement job kept its work (#3650). A reader cannot see whether keeping work saves runs. `devops_cli_service_implement_jobs_total` (#3069) counts each reported runner Job once by `result`, with no failure class and no `continued` outcome, and `devops_cli_service_implement_failures_total` holds the class alone. The counter `devops_cli_roadmap_pipeline_implement_total` that the issue names first does not exist, so the issue asks for `devops_cli_service_kept_work_total`.

## What Changes

- A clear rule of the Service keeps the class of the stop in the new record key `implement.continued` when the record holds `implement.wip` and the class is a member of `FailureClass`, and still removes `implement.failure`. Else the clear removes `implement.continued`.
- A new Service counter `devops_cli_service_kept_work_total` has the labels `repo`, `class` and `outcome`. `src/devops_cli/config/constants.py` names it, and `tests/grafana/test_grafana_dashboards.py` defers its panel to #3655.
- A round adds 1 to the counter with the outcome `continued` and the class in `implement.continued` when it creates the runner Job of an item whose record holds `implement.continued` and `implement.wip`.
- The report of that Job removes `implement.continued`. It adds 1 with the outcome `blocked` and the class of the new stop when it finds a stop, or with `finished` and the kept class when the result is `ready`. A `yielded` or `returned` report counts no outcome.
- `devops_cli_service_implement_jobs_total` and its requirement do not change: it still counts each reported runner Job once.
- The Service starts the counter at zero for each repository, each member of `FailureClass` and each outcome.
- `k8s/README.md` lists the counter and its label values, `docs/CLUSTER.md` names it, and `docs/TELEMETRY.md` is regenerated from `src/devops_cli/docs/generator.py`.
- The module docstring of `src/devops_cli/telemetry/instruments.py` names the Service counter `devops_cli_service_kept_work_total`, so the registry entry of the `devops_cli_` prefix keeps a task that names its declared path.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/record`: Kept work counts its outcome
- `roadmap-service-counters`: The Service starts the implement pipeline counters at zero

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/docs/generator.py`, `src/devops_cli/telemetry/instruments.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/TELEMETRY.md`, `k8s/README.md`, `docs/CLUSTER.md`
- Tests: `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_service_counter_series.py`

## Feasibility

- The probes of this run say, word for word: The path `k8s/README.md` is a file of the staging commit.
- The probes of this run say, word for word: The path `implement_submit.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_submit.py`. No commit in the history deleted or renamed it.
- `git grep devops_cli_roadmap_pipeline_implement_total` and `git grep devops_cli_service_kept_work_total` find no file of `src/`, `tests/`, `docs/` or `k8s/` on `origin/main` at 42fbc79e. So the scenario "Counter selection follows #3069" of the issue selects `devops_cli_service_kept_work_total`.
- `openspec/specs/roadmap-implement-job/record/spec.md:108:### Requirement: Implement job outcome counter` counts each runner Job that a round reports once, and `src/devops_cli/roadmap/implement/implement_submit.py:368:_emit_implement_metrics(repo, item, _outcome(state, failure), failure, new_tokens)` is the one call that does it. A kept-work result on that counter would count a Job that starts from kept work more than once, so the plan adds a counter of its own and changes neither.
- `src/devops_cli/roadmap/implement/implement_submit.py:428:labels={"repo": repo, "item_class": item_class, "result": result},` shows the 3 labels of the jobs counter. The 11 item classes of `CONST_BRANCH_TYPES` and its 3 results give 33 label sets for each repository. A label `class` with the 3 kept-work results would make 990, and the new counter has 3 for each member of `FailureClass`.
- `src/devops_cli/roadmap/implement/implement_submit.py:332:item = _fresh(store, item.number)`, `src/devops_cli/roadmap/implement/implement_submit.py:335:failure = _failure_of(`, `src/devops_cli/roadmap/implement/implement_submit.py:348:result = _attempt_result(item)` and `src/devops_cli/roadmap/implement/implement_submit.py:357:service_release(store, item.number, marks)` show that `_report` holds the record, the class of the new stop and the result before its release write. So it can read `implement.continued` and remove it in that write with no new request.
- `src/devops_cli/roadmap/implement/implement_submit.py:494:number = target.item.number`, `src/devops_cli/roadmap/implement/implement_submit.py:504:if not service_claim(store, number, marks):` and `src/devops_cli/roadmap/implement/implement_submit.py:507:jobs.create(` show that `_create` holds the item of the target and writes a claim before it creates the Job. So it can read `implement.continued` and `implement.wip`, and remove an old mark in the claim write.
- `src/devops_cli/roadmap/implement/implement_submit.py:579:stops = clear_stops(` comes before `src/devops_cli/roadmap/implement/implement_submit.py:610:created = _create(store, api, repo, plan.selected[0], label, size)`, so the clear writes the record in the same round that creates the next Job.
- `src/devops_cli/roadmap/stop_clear.py:320:ImplementRecordKey.FAILURE: None,` is in `_marks`, and `src/devops_cli/roadmap/stop_clear.py:356:status = write_status(store, current, facts, marks=_marks(decided, now)).status` is in `_clear_one`, which holds the item `current`. The clear removes the class, so the plan keeps the class in `implement.continued` at the clear.
- `src/devops_cli/roadmap/implement/implement_run.py:2042:ImplementRecordKey.FAILURE: klass.value,` and `src/devops_cli/roadmap/implement/implement_run.py:2058:marks[ImplementRecordKey.WIP] = _wip_record(self.wip)` show that a stop writes its class and its kept work in one write.
- `src/devops_cli/roadmap/implement/implement_run.py:726:written[ImplementRecordKey.WIP] = None` shows that a group that passes removes `implement.wip`. So `implement.wip` holds the kept work of the run that stopped and of no earlier run, and the report of a `ready` Job finds no `implement.wip`.
- `src/devops_cli/roadmap/failure.py:63:PROVIDER = "provider"` to `src/devops_cli/roadmap/failure.py:83:PLAN_UNREADABLE = "plan_unreadable"` are the members of the closed enum `FailureClass`. The label `class` takes only these values, because the clear keeps no class that is not a member, and the report counts `blocked` only with the class that `_failure_of` gives.
- `tests/grafana/test_grafana_dashboards.py:1003:deferred_metrics = {` and `tests/grafana/test_grafana_dashboards.py:1012:if name.startswith("CONST_SERVICE_METRIC_") and value not in deferred_metrics` show that a new `CONST_SERVICE_METRIC_` constant fails `test_cli_dashboard_service_row_reads_each_series_of_the_service` until the row charts it or the set defers it. So the constant and the set change in one group.
- `tests/roadmap/implement/test_roadmap_implement_record_readers.py:72:assert {key.value for key in ImplementRecordKey} == set(READERS)` and `tests/invariants/test_roadmap_workflow_doc.py:158:problems += [f"record key {key} is missing" for key in sorted(RECORD_KEYS - named_keys)]` fail while the enum holds a key that the table or the page does not name. So the enum member, the reader line and the row of `docs/ROADMAP_WORKFLOW.md` land in one group.
- `src/devops_cli/server/counter_series.py:87:({"class": klass.value, "repo": repo} for klass in FailureClass for repo in repo_names),` primes the failures counter with each member of `FailureClass`, the form that the kept-work counter follows. `src/devops_cli/server/counter_series.py:95:for result in ("succeeded", "failed", "gone")` primes the jobs counter, which does not change.
- `tests/telemetry/test_telemetry_instruments.py:81:("prefix", "devops_cli_", "src/devops_cli/telemetry/instruments.py"),` binds the `devops_cli_` prefix to the instruments module. The archived gate rule `openspec/changes/archive/2026-11-07-3254-list-the-registry-and-ratchet-entries/specs/roadmap-stage/spec.md:4:MUST refuse a plan that adds a counted item and has no task whose text names the declared path` therefore needs a task that names that path.
- The sentence at line 1021 of `src/devops_cli/docs/generator.py` gives the labels of the jobs counter. Group 4 adds the sentence of the kept-work counter after it, and then regenerates `docs/TELEMETRY.md`.
- `docs/CLUSTER.md:28:## Roadmap service` is the heading that the link of `k8s/README.md` names. From the folder `k8s/` the link is `../docs/CLUSTER.md#roadmap-service`.
- `k8s/README.md:602:## Alerting` and the other sections are sliced by their headings in the tests, and `k8s/README.md:1328:## Directory Structure` is the last section. So group 5 adds its section at the end of the file and edits no existing section.
- `run_implement_round` needs a client of the Kubernetes API, a client of the roadmap store and a checkout of the repository clone; `tests/roadmap/implement/test_roadmap_implement_submit.py` gives them with a fake cluster, an in-memory store and a repository under the temporary directory.
- `clear_stops` needs a client of the roadmap store for the comments of the issue and a read of the template of CronJob `devops-cli-runner` from the Kubernetes API; `tests/roadmap/test_roadmap_stop_clear.py` gives them with a fake store and a template function.
- `prime_service_counters` needs no checkout, no client and no network: it writes the in-memory registry of `GLOBAL_METRICS`.
- The plan introduces no command and no verify program: each verify runs `uv run devops ci test` or `uv run devops ci docs`, rows of the gate, and the runner image holds `uv`, `devops` and `pytest`.
- The failure classes of these commands are `test`, `lint`, `types` and `ci_infra`, each a member of `FailureClass` with an action in `ACTION_BY_CLASS`, so no failure class is new, and no verify needs a tool of the `NOT_IN_RUNNER` list.
- The tests reach no network, no cluster and no real scanner, and each writes under the temporary directory, so the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` hold.
- No open pull request changes a path of this plan, and the Dependencies section of the issue says None, so `dependencies` is empty.

## Existing Tool Considered

`GLOBAL_METRICS.increment_counter` and `GLOBAL_METRICS.prime_counter` cover the counter and its zero series, as `src/devops_cli/roadmap/implement/implement_submit.py` and `src/devops_cli/server/counter_series.py` use them, and `ImplementRecordKey` carries the new mark. The change adds no tool.

## Dependencies

None.
