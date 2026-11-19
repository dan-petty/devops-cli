# Proposal

## Why

Issue #3634 reports a metrics row that spent 627 to 1000 GitHub requests an hour after #3601, against 222 to 305 before it, because each new pod read the label events of every open Item again: the only copy of those times was the process dict `_item_label_times`. The 2000-request budget holds every row, so the age metrics crowd out the other rows, and each rollout adds to the cost. This change keeps those reads across pods and bounds them in one round.

## What Changes

- The label times of each open Item move from the process dict `_item_label_times` to `item-label-times.json` in the state directory of each repository, beside its `schedule.json`, written atomically by the new module `src/devops_cli/github/item_label_times.py`.
- Each entry holds the Item's `updated_at`, so a round sends no label-event request for an Item whose entry holds that value, also in a new pod.
- A round that keeps a record reads the label events of at most 20 Items (`_MAX_ITEM_AGE_READS_PER_ROUND`), the oldest entry first: an Item that the record does not hold, then an Item whose `updated_at` moved, by the `updated_at` of its entry. The Items that the cap defers keep their entry and wait for later rounds.
- A round writes the record with the entry of every open Item, drops the entry of each Item that left the open list, and logs one error that names the file when the write fails.
- The metrics row passes the `repo_dir` of its repository, which the due table already gives it, as the record path; `reset_item_age_cache` and its entry in the reset map of `tests/conftest.py` go.
- `devops gh metrics` keeps its read of every Item's label events, because it has no record file and the cap belongs to the row.
- A test measures one new pod at 24 GitHub requests in its first round over 30 open Items: the 4 fixed reads of the row plus the 20 label-event reads of the cap, and the pull request body states that number. The plan counted 25, because `METRICS_ROW_GITHUB_REQUEST_BUDGET` was 5 when it was planned; #6095 set it to 4.
- `docs/CLUSTER.md` names `item-label-times.json` in item 11 and gives the live check of the row's hourly cost in item 12.
- The spec delta of `project-metrics-dashboard` renames and rewrites the label-event requirement onto `updated_at`, and adds the record file, the cap of 20 label-event reads a round and the failed write.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-metrics-dashboard`: The row keeps the label times of each open Item, The row reads the label events of at most 20 Items in one round, A failed write of the record keeps the round, The label events of an Item are read when its updated_at moves

## Impact

- Code: `src/devops_cli/github/item_label_times.py`, `src/devops_cli/github/metrics.py`, `src/devops_cli/roadmap/run.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/github/test_item_label_times.py`, `tests/github/test_github_metrics.py`, `tests/github/test_github_metrics_request_budget.py`, `tests/conftest.py`, `tests/roadmap/test_roadmap_run_metrics.py`

## Feasibility

- The problem that came back says the earlier reply named reads and tools that this run did not make. Every line below names a call of this run and what it answered, and no line names a call that this run did not make.
- The probe says, word for word: The path `src/devops_cli/github/metrics.py` is a file of the staging commit.
- The probe gives the per-process cache, word for word: `_item_label_times` is defined at src/devops_cli/github/metrics.py:509:_item_label_times: dict[tuple[str, int], tuple[tuple[str | None, str | None], _LabelTimes]] = {}
- The probe names the names it did not check, word for word: Not probed, the bound of 10 commands is reached: `updated_at`, `keep_state_record`, `_MAX_ITEM_AGE_READS_PER_ROUND`, `item_label_times`, `devops_cli_github_requests_total`; this run checked `updated_at`, `_MAX_ITEM_AGE_READS_PER_ROUND` and `item_label_times` with the calls below, and it ran no search for `devops_cli_github_requests_total`, so that name is not checked.
- `read_file` of `src/devops_cli/github/metrics.py` lines 495 to 560 showed src/devops_cli/github/metrics.py:509:`_item_label_times: dict[tuple[str, int], tuple[tuple[str | None, str | None], _LabelTimes]] = {}` and src/devops_cli/github/metrics.py:538:`def _label_times(store: RoadmapStore, repo: str, items: list[Item]) -> dict[int, _LabelTimes]:`, keyed by `(repo, item.number)` on the values `(item.status, item.owner)`, which this change replaces.
- `read_file` of `src/devops_cli/github/metrics.py` lines 85 to 92 showed src/devops_cli/github/metrics.py:88:`METRICS_ROW_GITHUB_REQUEST_BUDGET: Final[int] = 5`, the staged constant of the row's fixed reads.
- `file_symbols` of `src/devops_cli/github/metrics.py` listed `reset_item_age_cache` at 515, `get_item_age_metrics` at 584, `_read_item_ages` at 661 and `collect_project_metrics_report` at 863.
- `search_code` for `_MAX_ITEM_AGE_READS_PER_ROUND` answered No match, and `search_code` for `item-label-times` answered No match, so the cap and the record file are new.
- `references` for `item_label_times` answered: files 2, lines 7; src/devops_cli/github/metrics.py at 509, 517, 546, 552 and 553, and the archived proposal of 2026-11-14-3794 at 26, so no file holds a module `item_label_times.py`.
- `references` for `reset_item_age_cache` answered: files 3, lines 4; src/devops_cli/github/metrics.py at 515 and 1088, tests/conftest.py at 120 and openspec/changes/archive/2026-11-05-2919-stuck-item-age-metrics-and-one/tasks.md at 37; the two live files are in the `changes` of group 2, and the archived task file stays as it is.
- `read_file` of `tests/conftest.py` lines 105 to 130 showed tests/conftest.py:120:`"reset_item_age_cache",` in the reset map, which group 2 drops.
- `read_file` of `src/devops_cli/roadmap/stores/store.py` lines 500 to 540 showed src/devops_cli/roadmap/stores/store.py:529:`updated_at: datetime | None = None` on `Item`, so an Item carries the issue's updated_at.
- `search_code` for `updated_at=self.updated_at` answered src/devops_cli/roadmap/stores/github_store.py:225:`updated_at=self.updated_at,`, so the store fills that field from the issue payload.
- `search_code` for `"updated_at": self._roadmap.clock()` answered tests/support/fakes/roadmap_store.py:965:`update = changes | {"updated_at": self._roadmap.clock()}`, so a write to an Item moves its updated_at and a label change gives a new version.
- `read_file` of `src/devops_cli/roadmap/phase.py` lines 215 to 250 showed src/devops_cli/roadmap/phase.py:234:`item_times = times.get(item.number) if times else None`, so an Item the cap does not read falls back to its record times and updated_at and raises nothing.
- `read_file` of `src/devops_cli/roadmap/stores/github_store.py` lines 860 to 885 showed src/devops_cli/roadmap/stores/github_store.py:863:`def label_changes(self, number: int) -> list[Change]:`, which reads the events listing of one issue through `_listing`, so one Item costs one events read.
- `read_file` of `src/devops_cli/output/file_writer.py` lines 195 to 215 showed src/devops_cli/output/file_writer.py:202:`def write_json_file(` with src/devops_cli/output/file_writer.py:207:`atomic: bool = True,`, so the record file gets an atomic write and no new writer.
- `read_file` of `src/devops_cli/roadmap/run.py` lines 925 to 960 showed src/devops_cli/roadmap/run.py:930:`def _run_metrics_adapter(` with src/devops_cli/roadmap/run.py:935:`**_: Any,`, so the `repo_dir` keyword that the due table passes reaches the row today and group 4 names it.
- `search_code` for `repo_dir=schedule_path.parent` answered src/devops_cli/roadmap/run.py:1271 and src/devops_cli/roadmap/run.py:1924:`repo_dir=schedule_path.parent,`; `read_file` of lines 1895 to 1935 showed the due table passing it to `row.runner` for every row, the metrics row included.
- `read_file` of `tests/github/test_github_metrics_request_budget.py` lines 1 to 95 showed tests/github/test_github_metrics_request_budget.py:48:`def _warm_ages(github: GitHubFake) -> None:` and tests/github/test_github_metrics_request_budget.py:61:`_warm_ages(github)`, so that budget test fills the process cache today; group 2 moves it onto the record file in the same step.
- `read_file` of `tests/github/test_github_metrics.py` lines 1405 to 1480 showed tests/github/test_github_metrics.py:1422:`def test_a_round_reads_an_items_label_events_only_when_its_status_or_owner_changes(` and tests/github/test_github_metrics.py:1447:`def test_a_round_of_one_repository_keeps_the_label_times_of_another(`, the two tests that group 2 rewrites.
- `callers` of `collect_project_metrics_report` answered src/devops_cli/commands/gh.py:2220 and src/devops_cli/roadmap/run.py:952, so a person's command calls the collection with no record file; the plan keeps that command's read of every Item's label events and puts the cap on the round that keeps a record.
- `read_spec` of `project-metrics-dashboard` listed the base requirement `The label events of an Item are read when its labels change`, and its text and its two scenarios `Two rounds with no change` and `A Status that changed`; the modified entry keeps both scenarios and the rename gives the new name.
- `read_spec` of `roadmap-service-limits`, requirement `The Service shows each state record that it could not write`, reads that `devops_cli_service_state_unkept` SHALL be 1 with the label `record` set to `budget`, `halt` or `ledger`, so a fourth value would contradict the living spec and the record is a file of the row instead.
- `read_file` of `tests/telemetry/test_telemetry_instruments.py` lines 70 to 90 showed tests/telemetry/test_telemetry_instruments.py:81:`("prefix", "devops_cli_", "src/devops_cli/telemetry/instruments.py"),`; the change adds no series there, so the registry count and its test stay as they are.
- `read_file` of `docs/CLUSTER.md` lines 40 to 45 showed docs/CLUSTER.md:42:`so each file has one writer` and docs/CLUSTER.md:43:`sum by (repo, row, method) (increase(devops_cli_github_requests_total{job="roadmap-service"}[1h]))`, the place of the record file and of the live check.
- `list_files` of `tests/github` and `tests/roadmap` showed `tests/github/test_github_metrics.py`, `tests/github/test_github_metrics_request_budget.py` and `tests/roadmap/test_roadmap_run_metrics.py` at the commit, so no group creates them.
- `find_issues` for `metrics row item label times` showed #3941 open; this change addresses item label times persistence across restarts and bounds them per round, which is independent.
- The probe answers that `design.md` is no file at the root of the staging commit, so the measured number goes into the pull request body, which the acceptance criterion of the issue names.
- `collect_project_metrics_report` needs a checkout of the repository at `root` for its git tags, and a client of GitHub with a network for the CI runs, the milestones, the open issues, the traffic and the label events.
- `get_item_age_metrics` and `GitHubRoadmapStore.label_changes` need a client of GitHub with a network, and no checkout.
- `_run_metrics_adapter` needs the clone of the job and a client of GitHub with a network, through the collection it calls.
- `item_label_times_path`, `read_item_label_times`, `keep_item_label_times` and `write_json_file` need a local path only, and no checkout, client or network.
- The verify programs are `uv run devops ci test <path>` and `uv run devops ci docs`; the runner image holds `uv`, `devops` and `pytest`, so none of them is NOT_IN_RUNNER, and a failing test is failure class `test` while a failing docs check is class `lint`.
- The pod sets readOnlyRootFilesystem true, so each verify writes under the data directory or the test temporary directory and not the image; runAsNonRoot true, allowPrivilegeEscalation false, capabilities.drop ALL and seccompProfile RuntimeDefault apply to each run.
- The live check of group 6 is not checked: two rollouts and a reading of the production counter need the cluster and the Service, and this run ran no command against them.

## Existing Tool Considered

No open tool or library keeps a per-item cache across a pod. The change reuses project code: `write_json_file` with an atomic write in `src/devops_cli/output/file_writer.py`, and the per-repository state directory that holds `schedule.json` in `docs/CLUSTER.md`. Written cost of the new module: about 40k tokens to build, about 3k tokens a quarter to keep and about 8k tokens to repair, over about 3 hours. The change deletes the process dict `_item_label_times` and `reset_item_age_cache`.

## Dependencies

None.
