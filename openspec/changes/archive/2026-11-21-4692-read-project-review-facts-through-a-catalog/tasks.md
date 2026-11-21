# Tasks

## 1. Behavior: the catalog loader and its JSON Schema

- [x] 1.1 Add the failing tests in `tests/roadmap/project_review/test_review_catalog.py`, on fixture catalogs only: a fact with no id names its index and `id`; a fact with no section names the fact and `section`; a section that `sections` does not list; two facts with one id; a disagreement that names an unknown fact; an unknown placeholder `{owner}`; a Service metric query with no `{repo}` names the fact; a query `by (node)` names the fact; the placeholders of a PromQL query for the 7 days to `2026-11-11T14:51:23Z` of `example/project` give `repo="example/project"` and `[604800s]` and keep the label braces
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_catalog.py`
- [x] 1.2 Add `src/devops_cli/roadmap/project_review/catalog.schema.json` (Draft 2020-12), `src/devops_cli/roadmap/project_review/catalog.py` (load with PyYAML, validate with `jsonschema`, the 3 cross-reference checks, frozen dataclasses, `render_query`), and the messages of each refusal in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_catalog.py`

## 2. Behavior: the merged pull requests and the read-only snapshot

- [x] 2.1 Add the failing tests: a merged pull request of the issue listing gives `merged_at` and a closed one gives null, in `tests/roadmap/stores/test_roadmap_github_store_items.py`; a read with `keep=False` reads the changes after the watermark and leaves the snapshot file as it was, in `tests/roadmap/stores/test_listing_snapshot.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_items.py tests/roadmap/stores/test_listing_snapshot.py`
- [x] 2.2 Add `merged_at` to `IssueRecord` in `src/devops_cli/roadmap/stores/store.py` and read it from `pull_request.merged_at` in `src/devops_cli/roadmap/stores/github_store.py`, with the public `listing()` of every issue and pull request; pin the new `LISTING_SCHEMA_KEY` in `tests/roadmap/stores/test_listing_snapshot.py`; add `keep: bool = True` to `IncrementalListing` in `src/devops_cli/roadmap/stores/listing_snapshot.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_items.py tests/roadmap/stores/test_listing_snapshot.py tests/roadmap/stores/test_roadmap_store_contract.py`

## 3. Behavior: Loki metric queries at a given time

- [x] 3.1 Add the failing test in `tests/k8s/test_logql_metrics.py`: `query_loki_metrics(..., at=<time>)` sends `time` with that instant, and a call with no `at` sends no `time`; answer from the HTTP fake
  - Verification: `$ uv run devops ci test tests/k8s/test_logql_metrics.py`
- [x] 3.2 Add the optional `at` parameter to `query_loki_metrics` in `src/devops_cli/k8s/logql.py`; its caller `src/devops_cli/roadmap/job_grade_report.py` keeps the current time and does not change
  - Verification: `$ uv run devops ci test tests/k8s/test_logql_metrics.py tests/roadmap/test_job_grade_report.py`

## 4. Behavior: the GitHub, listing, Prometheus and Loki readers

- [x] 4.1 Add the failing tests in `tests/roadmap/project_review/test_review_readers.py`: a fake session with 2,000 runs that answers each `created` slice with at most 1,000 runs and the real `total_count` gives each run id once, and each slice read to the end holds fewer than 1,000 runs; a slice of 1 s with 1,000 runs raises `RoadmapReviewError`; a newest-first release listing requests pages 1 and 2 only when page 2 holds a release before the window start; the listing reader with a snapshot at the watermark `2026-11-11T14:28:04Z` and one issue opened at `2026-11-11T14:40:00Z` in the changed listing gives that issue once and leaves the snapshot file as it was; the `prometheus` and `loki` readers send `time` set to the window end (recorded requests of the HTTP fake); `GitHubApiFake.serve` in `tests/support/fakes/github.py` answers a listing from its query
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py`
- [x] 4.2 Add `src/devops_cli/roadmap/project_review/readers.py` over `GitHubSession.pages`, `GitHubStore` with `IncrementalListing(keep=False)`, `PrometheusClient` and `query_loki_metrics`, with its messages in `src/devops_cli/lang/en/messages.py`, and the run cap and the OpenSpec worker count in `src/devops_cli/config/defaults.py`, each with its class in `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py tests/roadmap/test_roadmap_limit_classes.py`

## 5. Behavior: the OpenSpec reader

- [x] 5.1 Add the failing test in `tests/roadmap/project_review/test_review_openspec.py`, over the new recorded git scenario `review_openspec` of `tests/support/git_scenarios.py` (`tests/fixtures/git/review_openspec.json`): a fixture repository that archives one change with one ADDED and one MODIFIED requirement in the window gives 1 ADDED, 1 MODIFIED, and the totals 1 at the base and 2 at the head, and the checkout has no changed file after the read; a change that `openspec show` refuses (exit 1, "Change must have a Why section") is listed with that message and the totals stay; the answer of `openspec show` comes from the OpenSpec fake (`openspec_fake.script`)
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_openspec.py tests/core/test_git_contract.py`
- [x] 5.2 Add `src/devops_cli/roadmap/project_review/openspec_read.py`: the files that the window added under `openspec/changes/archive/` (`git diff --name-only -z --diff-filter=A`), their text at the head from one `git cat-file --batch`, each archived change that holds `specs/` written to `openspec/changes/` of a temporary root, `openspec show --json --deltas-only` through `isolated_openspec` in 4 workers with each refused change listed under `unread`, and `git grep -c` at the base and the head (the worker count is in `src/devops_cli/config/defaults.py` since 4.2); add its messages to `src/devops_cli/lang/en/messages.py` and the fact `openspec.unread_changes` to `src/devops_cli/roadmap/project_review/catalog.yaml`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_openspec.py tests/core/test_git_contract.py`

## 6. Behavior: the dispatcher, the status of each fact and data.json

- [x] 6.1 Add the failing tests in `tests/roadmap/project_review/test_review_dispatch.py`, on fixture catalogs: a window that ended 40 days ago marks each `prometheus` fact `expired` with a null value and a reason, and the HTTP fake records 0 requests; an unset `prometheus.url` marks the facts `skipped` with a reason that names the setting; a `scalar` query with an empty vector is `skipped`, not 0; a Loki answer of HTTP 500 marks the `loki` fact `error` and the `prometheus` fact stays `ok`; the stage SLI of `example/project` is 0.372 when the fixture Prometheus gives 0.927 for a query with no `repo` matcher; two facts on one releases query send one request for each page and each gets the value of its own `jq` program; three pairs that differ give three disagreements with both values, and a pair within the tolerance 0.1 gives none. In `tests/roadmap/project_review/test_review_facts.py`, add the test that `data.json` holds the git facts with the section `changes`, then the facts of a fixture catalog with their section, and the count of the reads of each reader kind
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_dispatch.py tests/roadmap/project_review/test_review_facts.py`
- [x] 6.2 Add `src/devops_cli/roadmap/project_review/dispatch.py`; add `section` to `Fact`, and `disagreements` and `collection` to `ReviewData`, in `src/devops_cli/roadmap/project_review/data.py`; give the git and lizard facts the section `changes` in `src/devops_cli/roadmap/project_review/facts.py`, and in the recorded result of `tests/fixtures/git/review_window.json`; call the dispatcher after the git facts in `run_review` of `src/devops_cli/roadmap/project_review/review.py`; add the messages of each reason in `src/devops_cli/lang/en/messages.py`; add `input_text` to the jq stub `typings/jq.pyi`; add the `path:` condition to `catalog.schema.json`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_dispatch.py tests/roadmap/project_review/test_review_facts.py tests/core/test_git_contract.py`

## 7. Behavior: the command and its dry run

- [x] 7.1 Add the failing tests in `tests/commands/test_roadmap_review.py`: `--last 7d --dry-run` lists each fact id of the catalog with its reader kind and rendered query, the process fake records 0 calls and `refuse_requests` records 0 requests; a run under the GitHub fake writes the git facts, then each catalog fact, each fact that is not `ok` with a reason. In `tests/roadmap/project_review/test_review_facts.py`, the summary shows each fact that is not `ok` with its reason and each disagreement (`render_review`)
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py tests/roadmap/project_review/test_review_facts.py`
- [x] 7.2 Add the catalog plan to `planned_review` and the disagreement lines to `render_review` in `src/devops_cli/roadmap/project_review/review.py`; update the docstring and the run of `src/devops_cli/commands/roadmap_review.py`; update the help of `review_run` and `review_dry_run` in `src/devops_cli/lang/en/help.py` and the placeholders in `src/devops_cli/lang/en/messages.py`; add the shared reads to `plan_catalog` in `src/devops_cli/roadmap/project_review/dispatch.py`; regenerate the command reference (`docs/commands/roadmap.md`)
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py`

## 8. Data: the shipped catalog

- [x] 8.1 Add `src/devops_cli/roadmap/project_review/catalog.yaml` with the sections, the retention of each reader kind (`prometheus` and `loki` 30d, `github_runs` 90d), the facts and the disagreements: the issues opened and closed, the merged pull requests and their lead-time median, the releases, the push runs of `main` by conclusion, the code-scanning alerts opened and fixed, the OpenSpec deltas by operation and the requirement totals, the alternatives checks, the Service SLIs of `{repo}` for each row, the SRE queries Q1 to Q16 and the Kubernetes queries Q2 to Q22 that `prometheus` can read (a recording rule where one gives the same value; no `by (node)` or `by (instance)`), the alert, notification, silence and Argo CD facts, the agentic job counters, the Renovate facts, one Loki `topk` over `count_over_time` fact, the gateway and CLI spend, and the 3 disagreements (implement counters, Service counter against kube-state-metrics, CLI spend against gateway spend)
  - Verification: `$ uv run devops roadmap review run --last 7d --dry-run`
- [x] 8.2 Check that the catalog holds no row of the usage-error counter
  - Verification: `$ ! git grep -n devops_cli_usage_error_total -- src/devops_cli/roadmap/project_review/catalog.yaml`

## 9. Other: the live numbers and the budget

- [x] 9.1 Run the review read-only from the worktree for `--version v0.111.0..v0.112.1` and for `--since 2026-11-04T14:51:23Z --until 2026-11-11T14:51:23Z`, with `prometheus.url` and `loki.url` set to short port-forwards for the run; compare each acceptance number of #4692 and name each number that differs with its reason; a source past its retention must be `expired`
  - Verification: `$ uv run devops roadmap review run --version v0.111.0..v0.112.1 --json`
- [x] 9.2 Run `--last 7d`, and measure the GitHub requests (the `collection` of `data.json`) and the elapsed time: 45 requests or fewer, and 3 min or less
  - Verification: `$ uv run devops roadmap review run --last 7d --json`

## 10. Documents

- [x] 10.1 Update the review line of `docs/ROADMAP_WORKFLOW.md`, the Purpose of `openspec/specs/roadmap-project-review/spec.md`, the docstring of `RoadmapReviewError` in `src/devops_cli/exceptions/roadmap.py` (and the generated `docs/ERRORS.md`), the `serve` of the GitHub fake in `docs/TESTING.md` and each other document that the change makes wrong (`git grep -n -i 'project review\|project_review' -- docs CONTEXT.md README.md`), and regenerate the generated documents
  - Verification: `$ uv run devops docs generate --check`

## 11. Behavior: the fixes of the review

- [x] 11.1 Add the failing tests in `tests/roadmap/project_review/test_review_readers.py`: a snapshot of this schema whose last full read is 3 days old gives only the listing changed since its watermark; with no snapshot, or one of another schema key, the reader sends only the listing changed since the window start; no snapshot file changes
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py`
- [x] 11.2 Give the review its own `ListingRead` in `src/devops_cli/roadmap/project_review/readers.py`, list both listing reads in the plan of `src/devops_cli/roadmap/project_review/dispatch.py` with the messages in `src/devops_cli/lang/en/messages.py`; add the `ListingRead` protocol and remove `keep` from `IncrementalListing` in `src/devops_cli/roadmap/stores/listing_snapshot.py`, take the protocol in `src/devops_cli/roadmap/stores/github_store.py`, and remove the `keep` test from `tests/roadmap/stores/test_listing_snapshot.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py tests/roadmap/stores/test_listing_snapshot.py tests/roadmap/stores/test_roadmap_github_store_items.py`
- [x] 11.3 Add the failing tests in `tests/roadmap/project_review/test_review_dispatch.py`: a window as long as the retention is read; an address that refuses each connection gets the attempts of one query and each fact is `error`; a Loki answer of `text/html` marks the `loki` fact `error` and the `prometheus` fact stays `ok`; a `rows` answer with no series and no base is `skipped`; an empty answer is none only when the base metric has a series. In `tests/k8s/test_logql_metrics.py`, an answer that is not JSON raises `KubernetesLoggingError` that names `loki.url`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_dispatch.py tests/k8s/test_logql_metrics.py`
- [x] 11.4 In `src/devops_cli/roadmap/project_review/dispatch.py`, read a start up to 1 hour before the retention limit, end the reads of a reader kind after a network error, and read the base metric of an empty answer; add `base` to `src/devops_cli/roadmap/project_review/catalog.py` and `src/devops_cli/roadmap/project_review/catalog.schema.json`; refuse an answer that is not JSON in `src/devops_cli/k8s/logql.py` with its message in `src/devops_cli/lang/en/errors.py`; give one time now to the window and the review in `src/devops_cli/commands/roadmap_review.py`; add the messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_dispatch.py tests/k8s/test_logql_metrics.py tests/commands/test_roadmap_review.py`
- [x] 11.5 Add the failing tests in `tests/roadmap/project_review/test_review_catalog.py`: each Service metric selector of a query, and a base metric of the Service, must hold `repo="{repo}"`; `{name_slug}` of `Example/My.Project` is `my-project`. In `tests/github/test_repo_ref.py`, the ad hoc name of a short name holds `name_slug` after the row
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_catalog.py tests/github/test_repo_ref.py`
- [x] 11.6 Add `RepoRef.name_slug` to `src/devops_cli/github/repo_ref.py`; add the placeholder `{name_slug}` and the check of each selector to `src/devops_cli/roadmap/project_review/catalog.py` and `catalog.schema.json`, the dry-run value to `src/devops_cli/roadmap/project_review/review.py`, and the messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_catalog.py tests/github/test_repo_ref.py tests/commands/test_roadmap_review.py`
- [x] 11.7 Add the failing test: the scenario `review_openspec` of `tests/support/git_scenarios.py` archives a `design.md` with CRLF, a lone carriage return and a byte that is not UTF-8 (`tests/fixtures/git/review_openspec.json`), and `tests/roadmap/project_review/test_review_openspec.py` checks the text of `design.md` and of the spec after it
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_openspec.py tests/core/test_git_contract.py`
- [x] 11.8 Read the archived files with one `git grep` of their lines in `src/devops_cli/roadmap/project_review/openspec_read.py` and in the plan of `src/devops_cli/roadmap/project_review/dispatch.py`; record `tests/fixtures/git/review_openspec.json` again
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_openspec.py tests/core/test_git_contract.py`

## 12. Data: the catalog fixes of the review

- [x] 12.1 In `src/devops_cli/roadmap/project_review/catalog.yaml`: count the implement Jobs of the repository by `devops-cli-implement-{name_slug}-...` and read both runner Job names in SLO 2 and the runner memory and CPU; define the stage facts as rounds and add `prometheus.stage_item_results` and `prometheus.stage_jobs`; rename `listing.alternatives_last_checked` and `prometheus.alternatives_rounds` and add `loki.alternatives_checks`; give each count and rows fact its `base`; cite the SRE and Kubernetes query lists in the header
  - Verification: `$ uv run devops roadmap review run --last 7d --dry-run`

## 13. Documents: the fixes of the review

- [x] 13.1 Keep the summary of `RoadmapReviewError` on one line in `src/devops_cli/exceptions/roadmap.py`; say in the description of `loki.url` in `src/devops_cli/config/settings.py` that the review dials no default address; regenerate `docs/ERRORS.md`, `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`; update the proposal, the design and the spec delta of this change
  - Verification: `$ uv run devops docs generate --check`

## Workflow follow-up

- #4840 adds the LogQL row of the CLI usage errors in section `self_improvement`, after #5219.
- #4714 reads the Alertmanager API to match a silence to an alert for the incident triggers.
- #5378 (comment of 2026-11-21): repair the three archived proposals with no Why section, and make the gate check the proposal form before the archive.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
