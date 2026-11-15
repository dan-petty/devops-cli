# Proposal

## Why

Issue #3634 reports a metrics row that spent 627 to 1000 GitHub requests an hour after #3601, against 222 to 305 before it, because each new pod read the label events of every open item again: the only copy of those times was the process dict `_item_label_times`. The budget of 2000 requests an hour holds every row, so the age metrics crowd out the other rows, and each rollout adds to the cost. This change keeps those reads across pods and bounds them in one round.

## What Changes

- The label times of each open Item move from the process dict to item-label-times.json in the state directory of each repository, beside its schedule.json, written atomically with one error log line when the write fails.
- Each entry carries the Item's `updated_at`, so a process that reads the file sends no label-event request for an Item the file holds at that value, also a new pod.
- A round reads the label events of at most 20 Items (`_MAX_ITEM_AGE_READS_PER_ROUND`), an Item whose `updated_at` moved before an Item that the file does not hold, and the Items that the cap defers keep their entry and wait for later rounds.
- A round writes the file with the entry of every open Item, the times it read and the entry it kept for an Item the cap deferred, and drops the entry of each Item that left the open item list.
- The metrics row passes the `repo_dir` of its repository, which the due table already gives it, to the collection as the record path; `reset_item_age_cache` and its entry in the reset map of `tests/conftest.py` go.
- The same step moves `tests/github/test_github_metrics_request_budget.py` onto the record file, so the 5-request budget test passes with the process dict gone.
- An offline test measures one new pod: 25 GitHub requests in its first round over 30 open Items, the 5 fixed reads of the row plus 20 label-event reads, and the pull request states that number.
- The counter `devops_cli_github_requests_total` stays as it is: the change adds no series, no label and no query, so the dashboards, the alert rules and the instrument registry stay unchanged.
- `docs/CLUSTER.md` names item-label-times.json in the state directory of each repository, and gives the live check of the row's hourly cost.
- The spec delta of `project-metrics-dashboard` renames and rewrites the label-event requirement onto `updated_at`, and adds the record file, the cap of 20 label-event reads a round, the kept entry of a deferred Item and the failed write.
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

- The probe answers, word for word: The path `src/devops_cli/github/metrics.py` is a file of the staging commit.
- The probe gives the per-process cache word for word: `_item_label_times` is defined at src/devops_cli/github/metrics.py:509:_item_label_times: dict[tuple[str, int], tuple[tuple[str | None, str | None], _LabelTimes]] = {}
- The probe names what it did not check: Not probed, the bound of 10 commands is reached: `updated_at`, `keep_state_record`, `_MAX_ITEM_AGE_READS_PER_ROUND`, `item_label_times`, `devops_cli_github_requests_total`; this run read them instead, as the lines below say.
- `read_file` of `src/devops_cli/github/metrics.py` lines 495 to 555 showed src/devops_cli/github/metrics.py:538:`def _label_times(store: RoadmapStore, repo: str, items: list[Item]) -> dict[int, _LabelTimes]:`, with the cache keyed by `(repo, item.number)` and the values `(item.status, item.owner)`, which this change replaces.
- `read_file` of `src/devops_cli/roadmap/stores/store.py` lines 501 to 535 showed src/devops_cli/roadmap/stores/store.py:529:`updated_at: datetime | None = None` on the class `Item`, and src/devops_cli/roadmap/stores/store.py:964:`def item_of(issue: IssueRecord) -> Item:`, which copies each issue field that Item holds, so an Item carries the issue's updated_at.
- `read_file` of `src/devops_cli/roadmap/stores/github_store.py` lines 215 to 232 showed src/devops_cli/roadmap/stores/github_store.py:225:`updated_at=self.updated_at,`, so the store fills that field from the issue payload.
- `search_code` for the fake's write answered tests/support/fakes/roadmap_store.py:965:`update = changes | {"updated_at": self._roadmap.clock()}`, so a write to an issue moves its updated_at and a label change gives a new version.
- `read_file` of `src/devops_cli/roadmap/phase.py` lines 219 to 248 showed src/devops_cli/roadmap/phase.py:234:`item_times = times.get(item.number) if times else None`, so an Item the cap does not read falls back to its record times and its updated_at and raises nothing.
- `search_code` for `def _run_metrics_adapter` answered src/devops_cli/roadmap/run.py:930, and `read_file` of lines 930 to 958 showed the signature ends in src/devops_cli/roadmap/run.py:935:`**_: Any,`, so the `repo_dir` keyword that the due table passes reaches the row today and the change names it.
- `search_code` for `repo_dir=schedule_path.parent` answered src/devops_cli/roadmap/run.py:1271 and src/devops_cli/roadmap/run.py:1924:`repo_dir=schedule_path.parent,`, so each row runner gets the state directory of its repository.
- `read_file` of `tests/github/test_github_metrics_request_budget.py` lines 48 to 80 showed tests/github/test_github_metrics_request_budget.py:48:`def _warm_ages(github: GitHubFake) -> None:` and tests/github/test_github_metrics_request_budget.py:61:`_warm_ages(github)`, so that budget test fills the process cache; group 2 deletes the cache and moves this helper onto the record file in the same step.
- `read_file` of `src/devops_cli/output/file_writer.py` lines 202 to 211 showed src/devops_cli/output/file_writer.py:202:`def write_json_file(` with src/devops_cli/output/file_writer.py:207:`atomic: bool = True,`, so the record file gets an atomic write and no new writer.
- The staged constant that the measurement relies on is src/devops_cli/github/metrics.py:88:`METRICS_ROW_GITHUB_REQUEST_BUDGET: Final[int] = 5`; `_MAX_ITEM_AGE_READS_PER_ROUND` is new, and this plan sets it to 20, so a cold round costs 5 plus 20, which is 25.
- `references` for `reset_item_age_cache` answered: files 3, lines 4; src/devops_cli/github/metrics.py at 515 and 1088, tests/conftest.py at 120, and openspec/changes/archive/2026-11-05-2919-stuck-item-age-metrics-and-one/tasks.md at 37; the two live files are in the `changes` of group 2, and the archived task file stays as it is.
- `references` for `item_label_times` answered: files 2, lines 7; src/devops_cli/github/metrics.py and the archived proposal of 2026-11-14-3794; the module name item_label_times.py is new, and no file of the staged commit holds it.
- The first finding of the earlier review is answered: the modified requirement `The label events of an Item are read when its updated_at moves` now holds the skip rule alone, about 280 characters, and the cap of 20 label-event reads a round moved to the added requirement `The row reads the label events of at most 20 Items in one round`, with its two scenarios.
- The second finding of the earlier review is answered: `read_file` of `tests/telemetry/test_telemetry_instruments.py` lines 75 to 82 showed tests/telemetry/test_telemetry_instruments.py:81:`("prefix", "devops_cli_", "src/devops_cli/telemetry/instruments.py"),`, the registry place of the `devops_cli_` prefix; group 6 reads that module and names it in its task, and the change adds no series there, so the registry count and its test stay as they are.
- `search_code` for `github_requests_total` answered that the counter is read in `docs/CLUSTER.md`, `docs/TELEMETRY.md`, the dashboards, the alert rules and the tests, and the plan changes none of those queries, so no registry count moves.
- `read_spec` of `project-metrics-dashboard` listed the base requirement `The label events of an Item are read when its labels change` with its two scenarios, `Two rounds with no change` and `A Status that changed`; the modified entry keeps both, so the delta replaces the whole base requirement.
- `collect_project_metrics_report` needs a checkout of the repository at `root` for its git tags, and a client of GitHub with a network for the CI runs, the milestones, the open issues, the traffic and the label events.
- `get_item_age_metrics` needs a client of GitHub with a network through `store.label_changes`, and no checkout.
- `_run_metrics_adapter` needs the clone of the job and a client of GitHub with a network, through the collection it calls.
- `read_item_label_times`, `keep_item_label_times` and `write_json_file` need a local path only, and no checkout, client or network.
- The verify programs are `uv run devops ci test <path>` and `uv run devops ci docs`, which run `uv`, `devops`, `pytest` and the docs checker of the runner image; none of them is NOT_IN_RUNNER. A failing test is failure class `test` and a failing docs check is class `lint`.
- The pod sets readOnlyRootFilesystem true, so each verify writes under the data directory and not the image; runAsNonRoot true, allowPrivilegeEscalation false, capabilities.drop ALL and seccompProfile RuntimeDefault apply to each run.
- The live check of group 6 is not checked: two rollouts and a reading of the production counter need the cluster and the Service, and this run ran no command against them.
- The issue cites a `design.md` at the repository root, and the probe answers, word for word: The path `design.md` is no file at the root of the staging commit; the measured number therefore goes into the pull request body, as the criterion says.
- #3941 is open, changes the same `collect_project_metrics_report` and the same request-budget test, and moves the reads of the row onto the conditional session, so it comes first and this plan rebases onto it.

## Existing Tool Considered

No open tool or library keeps a per-item cache across a pod, so the change builds its own record module on the project's own code: `write_json_file` with `atomic=True` of `src/devops_cli/output/file_writer.py`, and the per-repository state directory that holds `schedule.json`. Cost: about 40k tokens and 3 hours to build, about 3k tokens a quarter to keep, and about 8k tokens and 1 hour to fix. The change deletes the process dict `_item_label_times` and `reset_item_age_cache`.

## Dependencies

- #3941: it changes `collect_project_metrics_report` and the request-budget test of the metrics row, so it must merge first and this plan rebases onto it; the two changes then keep the 5-request budget and the 20-item cap apart.
- devops_cli_github_requests_total: the metric name is also held by `docs/CLUSTER.md`, `docs/TELEMETRY.md`, the devops-cli and roadmap-service dashboards, the alert rules of the Service, `tests/telemetry/test_telemetry_instruments.py`, `tests/grafana/test_grafana_dashboards.py`, `tests/prometheus/test_k8s_monitoring_alerting.py` and `tests/fixtures/dashboard_queries/devops-cli.yaml`; the change adds no series and alters no query, so each of them stays unchanged.
