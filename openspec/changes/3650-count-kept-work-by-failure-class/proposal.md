# Proposal

## Why

No metric shows what happens to an item after the implement job kept its work (#3650). A reader cannot see whether keeping work saves runs. #3069 counts each reported runner Job by `result`, but that counter holds no failure class and no `continued` outcome, and `devops_cli_service_implement_failures_total` holds the class alone.

## What Changes

- A clear rule of the Service keeps the class of the stop in `implement.continued` when the item record holds `implement.wip`, and still removes `implement.failure`.
- A round adds 1 to `devops_cli_service_implement_jobs_total` with the result `continued` and that class when it creates the runner Job of an item that holds kept work.
- A round adds 1 with the result `finished` when the report of that Job finds the ready mark, and with the result `blocked` and the class of the new stop when it finds a stop, and clears `implement.continued`.
- `devops_cli_service_implement_jobs_total` gains the label `class`: the failure class that an increment counts, or `none` when it counts none. It still counts every reported runner Job once.
- The Service starts the kept-work label sets at zero: `none` and each failure class for `continued`, `finished` and `blocked`, `none` for `succeeded` and `gone`, and `none` and each failure class for `failed`.
- `k8s/README.md` lists the counter and its label values, `docs/CLUSTER.md` names the new label, and `docs/TELEMETRY.md` is regenerated from `src/devops_cli/docs/generator.py`.
- The module docstring of `src/devops_cli/telemetry/instruments.py` names the Service counter `devops_cli_service_implement_jobs_total` with its labels, so the registry entry of the `devops_cli_` prefix keeps a task that names its declared path.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/record`: Kept work counts its outcome, Implement job outcome counter
- `roadmap-service-counters`: The Service starts the implement pipeline counters at zero

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/docs/generator.py`, `src/devops_cli/telemetry/instruments.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/TELEMETRY.md`, `k8s/README.md`, `docs/CLUSTER.md`
- Tests: `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/telemetry/test_service_counter_series.py`

## Feasibility

- The probes of this run say, word for word: The path `k8s/README.md` is a file of the staging commit.
- The probes of this run say, word for word: The path `implement_submit.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_submit.py`. No commit in the history deleted or renamed it.
- `search_code devops_cli_service_implement_jobs_total` found the counter of #3069 in the tree: `docs/TELEMETRY.md:64:The labels of `devops_cli_service_implement_jobs_total` are `repo`, `item_class` and `result`.` and `docs/CLUSTER.md:43:devops_cli_service_implement_jobs_total`, so the fallback counter of the issue does not apply and the plan reuses that counter.
- `read_spec roadmap-implement-job/record` gave the base requirement `Implement job outcome counter`, word for word: `The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class` and `result` once for each runner Job that a round reports.` The added requirement forbids only the results `continued`, `finished` and `blocked` for an item with no kept work, so the once-for-each-reported-Job increment of the base requirement stands and the two requirements agree.
- `read_spec roadmap-implement-job/record` with the requirement `The metric labels are classes of the taxonomy` gave: `Each panel and alert rule of `k8s/` that reads `devops_cli_service_implement_failures_total` SHALL match the label `class` only with values of the taxonomy.` The bounded label values of `class` therefore stay in the base spec, and the added requirement keeps its text under the length limit by leaving the fixed-set sentence to that requirement.
- `read_file src/devops_cli/roadmap/implement/implement_submit.py` lines 416 to 445 showed `src/devops_cli/roadmap/implement/implement_submit.py:422:labels={"repo": repo, "item_class": item_class, "result": result},` and `src/devops_cli/roadmap/implement/implement_submit.py:440:labels={"class": failure.value, "repo": repo},`, so the jobs counter holds no failure class and no kept-work outcome.
- `read_file` of the same file lines 474 to 521 showed `src/devops_cli/roadmap/implement/implement_submit.py:488:number = target.item.number` and `src/devops_cli/roadmap/implement/implement_submit.py:501:jobs.create(`, so `_create` holds the item of the target and reads its record before it creates the Job.
- `read_file` of the same file lines 316 to 384 showed `src/devops_cli/roadmap/implement/implement_submit.py:335:failure = _failure_of(` and `src/devops_cli/roadmap/implement/implement_submit.py:351:service_release(store, item.number, marks)`, so `_report` holds the class of the new stop and releases the item before it emits the metrics.
- `read_file` of the same file lines 555 to 615 showed `src/devops_cli/roadmap/implement/implement_submit.py:573:stops = clear_stops(` before `src/devops_cli/roadmap/implement/implement_submit.py:604:created = _create(store, api, repo, plan.selected[0], label, size)`, so the clear writes the record in the same round that creates the next Job.
- `read_file src/devops_cli/roadmap/stop_clear.py` showed `src/devops_cli/roadmap/stop_clear.py:320:ImplementRecordKey.FAILURE: None,` inside `_marks`, and `src/devops_cli/roadmap/stop_clear.py:356:status = write_status(store, current, facts, marks=_marks(decided, now)).status` in `_clear_one`, which holds the item `current`. The clear therefore removes the class and already holds the item that writes it, so the plan keeps the class in `implement.continued` at the clear instead of reading `implement.failure` later.
- `read_file src/devops_cli/roadmap/implement/implement_run.py` lines 1990 to 2035 showed `src/devops_cli/roadmap/implement/implement_run.py:2016:ImplementRecordKey.FAILURE: klass.value,` and `src/devops_cli/roadmap/implement/implement_run.py:2032:marks[ImplementRecordKey.WIP] = _wip_record(self.wip)`, so a stop writes its class and its kept work in one write.
- `read_file` of the same file line 715 to 740 showed `src/devops_cli/roadmap/implement/implement_run.py:724:written[ImplementRecordKey.WIP] = None`, so `implement.wip` holds the kept work of the run that stopped and of no earlier run.
- `read_file tests/roadmap/implement/test_roadmap_implement_record_readers.py` showed `tests/roadmap/implement/test_roadmap_implement_record_readers.py:17:from devops_cli.roadmap.stores.store import ImplementRecordKey`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py:72:assert {key.value for key in ImplementRecordKey} == set(READERS)` and `tests/roadmap/implement/test_roadmap_implement_record_readers.py:38:"implement.check": ("text", DOCUMENT, "The check that failed in the stop")`, so a new key needs a line of the table and a line may name a text of `docs/ROADMAP_WORKFLOW.md`.
- `read_file tests/invariants/test_roadmap_workflow_doc.py` lines 120 to 175 showed `tests/invariants/test_roadmap_workflow_doc.py:158:problems += [f"record key {key} is missing" for key in sorted(RECORD_KEYS - named_keys)]`, so the enum member and its row of `docs/ROADMAP_WORKFLOW.md` land in one group.
- `read_file docs/ROADMAP_WORKFLOW.md` lines 158 to 180 showed `docs/ROADMAP_WORKFLOW.md:173:The count of the Jobs that the Service made to continue a run that ended with no result`, the row shape that the row of `implement.continued` follows.
- `read_file src/devops_cli/server/counter_series.py` lines 60 to 135 showed `src/devops_cli/server/counter_series.py:95:for result in ("succeeded", "failed", "gone")` with no `class` label, and `src/devops_cli/server/counter_series.py:117:{"repo": repo, "result": result, "class": klass}` as the shape that the stage jobs counter already primes.
- `read_file src/devops_cli/roadmap/failure.py` lines 58 to 81 counted 21 members of `FailureClass`, from `src/devops_cli/roadmap/failure.py:61:PROVIDER = "provider"` to `src/devops_cli/roadmap/failure.py:81:PLAN_UNREADABLE = "plan_unreadable"`; the plan allowlists all 21 as values of the label `class` with the reason that each is a member of the closed enum, and allowlists `none` for an increment that counts no class, so no other value is written and no member is removed or restricted.
- `read_file tests/telemetry/test_telemetry_instruments.py` lines 79 to 82 showed `tests/telemetry/test_telemetry_instruments.py:81:("prefix", "devops_cli_", "src/devops_cli/telemetry/instruments.py"),`, the registry entry that binds the `devops_cli_` prefix to the instruments module, and the archived gate rule reads `openspec/changes/archive/2026-11-07-3254-list-the-registry-and-ratchet-entries/specs/roadmap-stage/spec.md:4:MUST refuse a plan that adds a counted item and has no task whose text names the declared path.`
- `file_symbols src/devops_cli/telemetry/instruments.py` listed `src/devops_cli/telemetry/instruments.py:class Instrument` at line 30, `src/devops_cli/telemetry/instruments.py:def emit` at line 975 and `src/devops_cli/telemetry/instruments.py:def bounded_label` at line 995, and `search_code devops_cli_service_implement_jobs_total` gave no hit in that file, so the module gains one sentence of its docstring that names the Service counter and no instrument.
- The issue cites `k8s/README.md` for the failures counter, and `references devops_cli_service_implement_failures_total` listed 26 files with no `k8s/README.md`: the Service metrics moved to `docs/CLUSTER.md:43`, so the list that the acceptance criterion asks for is new text in `k8s/README.md`, and group 5 adds it.
- `search_code ## Alerting` showed `k8s/README.md:571:## Alerting`, and `tests/prometheus/test_k8s_monitoring_alerting.py` slices the sections of that file by their headings, so group 5 adds its section at the end of the file and edits no existing section.
- `search_code The labels of` showed `src/devops_cli/docs/generator.py:1021:The labels of `devops_cli_service_implement_jobs_total` are `repo`, `item_class` and `result`.`, the sentence that group 4 changes before `docs/TELEMETRY.md` is regenerated.
- The merge state of #3069 is not checked in this run; `docs/TELEMETRY.md:64` and `src/devops_cli/roadmap/implement/implement_submit.py:422` show its counter in the tree, which is the fact that the plan needs.
- `run_implement_round` needs a client of the Kubernetes API, a client of the roadmap store and a checkout of the repository clone; `tests/roadmap/implement/test_roadmap_implement_submit.py` gives them with a fake cluster, an in-memory store and a repository under the temporary directory.
- `_report` needs a client of the Kubernetes API for the log and the exit status of the pod and a client of the roadmap store; `_create` needs a client of the Kubernetes API; the same test module gives both.
- `clear_stops` needs a client of the roadmap store for the comments of the issue and a read of the template of CronJob `devops-cli-runner` from the Kubernetes API; `tests/roadmap/test_roadmap_stop_clear.py` gives them with a fake store and a template function.
- `prime_service_counters` needs no checkout, no client and no network: it writes the in-memory registry of `GLOBAL_METRICS`.
- The plan introduces no command and no verify program: each verify runs `uv run devops ci test` or `uv run devops ci docs`, rows of the gate, and the runner image holds `uv`, `devops` and `pytest`.
- The failure classes of these commands are `test`, `lint`, `types` and `ci_infra`, each a member of `FailureClass` with an action in `ACTION_BY_CLASS`, so no failure class is new, and no verify needs a tool of the `NOT_IN_RUNNER` list.
- The tests reach no network, no cluster and no real scanner, and each writes under the temporary directory, so the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` hold.
- The context lists no overlap and no metric sender, and the Dependencies section of the issue says None, so `dependencies` is empty.

## Existing Tool Considered

`GLOBAL_METRICS.increment_counter` and `GLOBAL_METRICS.prime_counter` cover the counter and its zero series, as `src/devops_cli/roadmap/implement/implement_submit.py` and `src/devops_cli/server/counter_series.py` use them, and `ImplementRecordKey` carries the new mark. The change adds no tool.

## Dependencies

None.
