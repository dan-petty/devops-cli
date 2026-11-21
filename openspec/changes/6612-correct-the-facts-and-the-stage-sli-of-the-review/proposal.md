# Proposal: #6612

## Why

The second review of PR #6586 (#4692) found six defects in the fact catalog of the project review (`src/devops_cli/roadmap/project_review/catalog.yaml`) and its dispatcher (`dispatch.py`). Each defect gives `ok` with 0 or no rows for a value that the review did not measure, or gives a false disagreement (#6612):

1. The `base` of `prometheus.tool_limit_hits` and of `prometheus.stage_gate_refusals` names a metric that the query does not read. The probe finds that other metric, so a window from before the queried counter existed gives `ok` with `[]` or `0.0`.
2. The probe of the base reads the whole window. Nine facts read their query only at the window end. When the series is absent at the end, the fact gives `ok` with no rows.
3. The pair `runner_jobs` compares `prometheus.implement_runner_jobs` with `prometheus.runner_jobs_started`, which counts only the Job names of #5739. A window that crosses the rename gives a false disagreement.
4. The condition `path:openspec/specs` reads the working tree, not the commits of the window. A window from before 2026-10-23 gives `openspec.requirements` `ok` with 0 and 0.
5. No code emits the gauge of `prometheus.oldest_pending_update` before #4911. Each review gives `skipped` with "No series matched the query.", which looks like a gauge that stopped.
6. The owner decided on 2026-11-21 (comment on #4692) that SLO 1 of the stage row counts item outcomes. `prometheus.stage_sli` still divides the Service rounds of `devops_cli_service_jobs_total`, and since #5559 a round plans no item.

## What Changes

- The loader refuses a fact whose `base` metric does not occur in its query. The new optional field `base_reason` lets a fact use another metric on purpose, and says why. Three shipped facts need it (`prometheus.colon_rules`, `prometheus.alerts_firing_hours`, `prometheus.oom_kills_devops`): their query has a series only when a thing happens, so the base is another metric. `prometheus.tool_limit_hits` takes the base `devops_cli_roadmap_tool_cuts_total`, and `prometheus.stage_gate_refusals` takes the base `devops_cli_roadmap_stage_gate_refusals_total`. That counter has the label `repo`, so its query and base also read the repository of the review.
- The probe has the time scope of the query. A query with the placeholder `{range}` keeps the probe `group(last_over_time(<base>[<range>]))`. A query with no `{range}` reads the end of the window, so its probe is `group(<base>)` at the window end.
- The new optional field `not_before` gives the first time of the series of a fact. A window that starts before it gives the fact `skipped` with a reason that names the time, and sends no request for it. `prometheus.runner_jobs_started` takes the time when the Job names of #5739 were live. The disagreement list already compares only two `ok` facts, so the pair is not listed for such a window.
- A `path:` condition reads the base and the head commits of the window with `git ls-tree`, through the git readers of the review (#4686). A path that is not at one of the commits gives `skipped` with a reason that names the path and the commit. The dry run lists the two git commands.
- The new optional field `no_series_reason` gives the reason of `skipped` when the query of a fact with no `base` matches no series. `prometheus.oldest_pending_update` says that the gauge comes with #4911. The text is catalog data, not code.
- `prometheus.stage_sli` becomes the share of the stage items of the repository that ended `staged` or `needs_split`, over the items of `devops_cli_roadmap_stage_total` that ended with a result other than `skipped`. Its definition names the owner decision of 2026-11-21 on #4692.
- The command output, `data.json` and the catalog form change, so the change modifies the capability `roadmap-project-review`.

## Capabilities

- `roadmap-project-review` (modified): the base metric rule, the time scope of the probe, the first time of a series, the path condition at the commits of the window, the reason of a missing series, and the stage SLI by item outcomes.

## Impact

- A review of a window from before a counter existed, or with a series absent at the window end, gives `skipped` with a reason in place of a false `ok`. A window across the Job rename of #5739 gives `prometheus.runner_jobs_started` `skipped` and no false disagreement. A window from before `openspec/specs` existed gives the OpenSpec facts `skipped`.
- `prometheus.stage_sli` changes its value and its meaning: items, not rounds. `prometheus.stage_successes` and `prometheus.stage_errors` keep the rounds.
- `prometheus.stage_gate_refusals` gives the refusals of the repository of the review only.
- A review of a window with the condition `path:` starts two more git commands (`git ls-tree`), each once for each path.
- A catalog that a person writes later is refused when its base metric does not occur in its query and it gives no `base_reason`.
- No new setting, no new dependency, no change to a config file or a manifest. Messages change, so `devops docs generate` writes the generated documentation again.
- The change fits one pull request. It builds on #6615 (PR #6629, merged on 2026-11-21), which changed the same catalog and dispatcher.

## Feasibility

Each defect exists on origin/main 3f8f7a90e (read on 2026-11-21):

- `catalog.yaml` lines 818 to 833: `prometheus.tool_limit_hits` queries `devops_cli_roadmap_tool_cuts_total` with the base `devops_cli_roadmap_tool_calls_total`, and `prometheus.stage_gate_refusals` queries `devops_cli_roadmap_stage_gate_refusals_total` with the base `devops_cli_roadmap_stage_total`. `docs/TELEMETRY.md` line 176 gives the label `repo` of the refusals counter, and line 154 gives no label `repo` to the cuts counter.
- Census of the shipped catalog (a probe of the plan run that parses `catalog.yaml`): 83 facts, 67 `prometheus`, 42 with a `base`. The base metric does not occur in the query of 5 facts: the two facts of the issue and `prometheus.colon_rules`, `prometheus.alerts_firing_hours` and `prometheus.oom_kills_devops`. 9 facts with a `base` have no `{range}` in their query: `alert_rules`, `colon_rules`, `alertmanager_alerts`, `silences_active`, `argocd_apps`, `requests_over_allocatable`, `no_memory_limit`, `no_memory_request` and `valkey_no_maxmemory`, the nine facts of the issue. 4 more facts with a `base` read the window with a subquery `[{range}:5m]` (`stage_peak_hour`, `alerts_firing_hours`, `pending_pods`, `gpu_memory`), so they keep the range probe.
- `dispatch.py` line 102: `_PROBE = "group(last_over_time({base}[{range}]))"` for each fact. Lines 197 to 200: `_unmet` tests `(context.checkout / path).exists()`, the working tree.
- `catalog.yaml` lines 372 to 385 and 885 to 893: `prometheus.runner_jobs_started` matches only `devops-cli-implement-{name_slug}-...`, and the pair `runner_jobs` names it. `disagreements` in `dispatch.py` (lines 342 to 365) skips a pair when a side is not an `ok` number. PR #5739 closed #4558; the release comment on #4558 says "Live since 2026-11-14 22:29 UTC" (release v0.144.0).
- `git log -1 f209f6c89` gives 2026-10-23 for the commit that added `openspec/specs`. `git cat-file -e <rev>:<path>` exits 128 both for a path that is not there and for a commit that does not exist, but `git ls-tree --name-only <rev> -- <path>` exits 0 with no output for a path that is not there, and 128 for a commit that does not exist (git, run in this repository).
- `catalog.yaml` lines 855 to 861: `prometheus.oldest_pending_update` reads `devops_cli_dependency_update_oldest_pending_seconds`. `git grep -n oldest_pending -- src` finds only the catalog. #4911 is open.
- `catalog.yaml` lines 236 to 249: `prometheus.stage_sli` divides `devops_cli_service_jobs_total` rounds. `StageResult` (`src/devops_cli/roadmap/stage/stage.py`) gives the results `staged`, `needs_split`, `failed`, `degenerate` and `skipped` of `devops_cli_roadmap_stage_total`, with the label `repo`.
- `promtool` 3.16.0 is on the PATH of the devcontainer, and CI copies it from the devtools image (`.github/workflows/ci.yml`). `tests/support/promtool.py` runs it for tests marked `@pytest.mark.live("promtool")`.

## Existing Tool Considered

- The alternatives check of 2026-11-21 gives the verdict `none`. cloudflare/pint (Apache-2.0) lints the rules of Prometheus rule files, not this catalog. slok/sloth (Apache-2.0) writes SLO recording rules and does not read the facts of a review. promql-parser (PyPI) parses PromQL, but its PyPI release states no license, and the base rule needs only the leading metric name of a selector, which the schema pattern of `base` already fixes.
- The change uses promtool (Apache-2.0, maintained by the Prometheus project) to test the query of `prometheus.stage_sli`: `promtool test rules` evaluates the real PromQL over fixture series, with no network.
- The change builds the rest in the existing loader and dispatcher: one regular expression for the base rule, one more probe form, one time compare, one git command through the existing `run_git`, and three catalog fields. Cost: about 200,000 model tokens to build, test and keep, and about 5 hours elapsed. The cost to keep is small: about 60 lines of code and 3 schema fields.
- The change deletes the working tree test of `_unmet` and the message "The checkout holds no {path}.".
