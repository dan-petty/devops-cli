# Task: Roadmap job scheduling, due table evaluation, and checkout management (`devops roadmap run`) (#981)

**Issue**: [#981](https://github.com/dan-petty/devops-cli/issues/981)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/feature, scope/roadmap, priority/p1-high

## Description

`devops roadmap run` is the scheduler and runner for roadmap jobs (`intake`, `close`, `reprioritize`, and later `refine`). It evaluates the due conditions across jobs in a fixed order, passes outcomes as triggers to downstream jobs in the same run, records each job's last successful execution timestamp in `<data dir>/roadmap/<owner>/<name>/schedule.json`, and manages clean git clones at `<data dir>/roadmap/<owner>/<name>/clone` synced to `origin/release/vX.Y.Z` for jobs that require repository checkouts.

- **Due table**: One centralized table in `src/devops_cli/roadmap/run.py` holding job rows: name, interval (60m for `intake` and `close`), batch keys, change predicates, and cross-job predicates. In `DEFAULT_DUE_TABLE`, the landed jobs are `intake`, `close`, and `reprioritize`. `refine` (#744) is stubbed in test tables until it lands.
- **State tracking**: `<data dir>/roadmap/<owner>/<name>/schedule.json` holds the last-success ISO 8601 timestamp per job per repository, serving as both the interval reference and the cutoff cursor for `changes_since`. A failed job leaves its timestamp untouched so that it is retried on the next tick with the same changes.
- **Git clone management**: `ensure_checkout` maintains a clone at `<data dir>/roadmap/<owner>/<name>/clone`. It clones if missing, fetches `origin`, checks out `release/vX.Y.Z`, resets hard to `origin/release/vX.Y.Z`, and configures `user.name` and `user.email` from `session.login`. Clones and state files are validated against directory traversal and forbidden system paths (`CONST_FORBIDDEN_SYSTEM_DIRS`).
- **CLI and MCP modes**: `devops roadmap run` takes `--repo`/`-R`, `--dry-run`, and `--confirm`. Without `--confirm` or with `--dry-run`, it prints `Due: ...` and makes no modifications. With `--confirm`, it runs the due jobs. `roadmap_run` FastMCP tool runs with `--dry-run` and returns the due job tuple without mutating store state.
- **Service integration**: `service_job(batch, table=..., clone_dirname=...)` in `src/devops_cli/roadmap/run.py` opens the roadmap store and dispatches the coalesced trigger batch to `run_due_jobs` with one lane's rows and clone. `devops serve --service` passes each lane's job to `create_service_app(jobs=SERVICE_JOBS)` (#1532).

## Acceptance Criteria

- [x] **Due table**: `tests/test_roadmap_run.py::test_due_table_scenarios` asserts the ordered tuple of jobs that ran across intervals (59m idle, 61m due), first-run without schedule, batch keys, issue reopen events, issue closure on current release, unlabeled/outside-release events, store actor changes, closure item outcomes, and refinement triggers.
- [x] **Webhook or poll**: `tests/test_roadmap_run.py::test_webhook_or_poll_identical_and_oldest_cutoff` verifies that both webhook and poll trigger batches identify the same `REOPENED` trigger with exactly one `changes_since` call using the oldest cutoff among rows.
- [x] **Order and cross-job triggers**: `tests/test_roadmap_run.py::test_order_and_cross_job_triggers` verifies 4-job stub table execution order (`intake`, `close`, `reprioritize`, `refine`), cross-job triggering from closure to reprioritize and intake to refine, and self-trigger prevention on second call.
- [x] **Failure**: `tests/test_roadmap_run.py::test_failure_isolation_and_cli_exit` verifies that a failed stub job does not prevent subsequent due jobs from executing, leaves the failed job's cutoff time unchanged in `schedule.json`, raises `RoadmapRunError` naming the failed jobs, and causes CLI under `CliRunner` to exit 1 and report the failed job.
- [x] **State file**: `tests/test_roadmap_run.py::test_state_file_persistence` verifies persistence in `schedule.json` and ensures a subsequent run 30m later sees intake not due.
- [x] **Checkouts**: `tests/test_roadmap_run.py::test_checkouts_git_management` verifies bare remote cloning to `<data dir>/roadmap/<owner>/<name>/clone`, tip tracking of `origin/release/vX.Y.Z`, author identity configuration, and clone failure isolation where intake and reprioritize succeed while clone-dependent jobs fail and are reported in `RoadmapRunError`.
- [x] **Idle**: `tests/test_roadmap_run.py::test_idle_records_zero_or_one_store_calls` verifies that an empty batch records zero store calls, and an empty poll batch with no changes records exactly one `changes_since` call.
- [x] **No prompt**: `tests/test_roadmap_run.py::test_no_prompt_and_cli_modes` verifies that stub runners receive no confirm argument, and `devops roadmap run` without `--confirm` or with `--dry-run` previews due jobs while `--confirm` executes them.
- [x] **Service wiring**: `tests/test_roadmap_run.py::test_service_wiring` verifies `devops serve --service` passes `SERVICE_JOBS` to `create_service_app` and each lane's job opens the store and invokes `run_due_jobs` with its rows and clone.
- [x] **MCP mirror**: `tests/test_roadmap_run.py::test_mcp_mirror_roadmap_run` verifies that FastMCP tool `roadmap_run` executes in dry-run mode, returns due job tuple, and mutates zero store state. `tests/test_fastmcp_contracts.py` and `tests/test_docs_mcp_argv_collector.py` verify tool registration and argv contracts.
- [x] **Help**: `tests/test_all_commands_help_dryrun.py` verifies help registration; `devops docs check` confirms all generated reference documentation is up to date.
- [x] **Shared files untouched**: `CHANGELOG.md` and `docs/ROADMAP.md` remain untouched; changelog fragment added at `changelog.d/981.md`.
- [x] **CI Quality Gate**: `uv run devops ci` completes with all quality checks passing.
- Pending a person, **Identity**: open a test issue in a managed repo. Within 5 minutes, `gh issue view <n> -R <owner>/<repo> --json comments --jq '.comments[-1].author.login'` prints the machine account's login, and the item's Value and Effort are set on the board (intake estimates them with the gateway models, #742, so this shows the gateway works through devops-cli's own client). Then close the issue as not planned.
- Pending a person, **Missed webhook**: in the repo's webhook settings, clear "Active". Add a test issue to a milestone, which the store reports as `joined_release`. Within 10 minutes, `kubectl -n devops logs deploy/roadmap-service --since=10m` shows a poll for that repo that reports the change and the job it made due. Then set the webhook active again.
- Pending a person, **Restart**: note the last intake time in the logs, then run `kubectl -n devops rollout restart deploy/roadmap-service`. After the pod is Ready, `kubectl -n devops exec deploy/roadmap-service -- cat /home/devops/.data/roadmap/<owner>/<repo>/schedule.json` shows that time, and intake does not run again within an hour of it. That one copy runs at a time during the restart is #1083's Rollout check.
- Pending a person, **Rate budget**: after a quiet hour, run in the pod, so the token never leaves the cluster: `kubectl -n devops exec deploy/roadmap-service -- python -c 'import json, os, urllib.request as u; r = u.Request("https://api.github.com/rate_limit", headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"]}); d = json.load(u.urlopen(r, timeout=10))["resources"]; print(d["core"]["used"], d["graphql"]["used"])'`. It prints two numbers under 2,500, half of a classic token's 5,000 per hour.

## Decisions and deviations

- **Landed vs unlanded jobs**: `DEFAULT_DUE_TABLE` includes only the three landed jobs in `release/v0.2.26` (`intake`, `close`, and `reprioritize`). `build_stub_table` provides a 4-job table for testing cross-job cascades to `refine` and clone failure isolation across multiple clone-dependent jobs.
- **Complexity decomposition**: `run_due_jobs` is decomposed into focused helpers (`_is_initial_idle`, `_fetch_filtered_changes`, `_simulate_dry_run`, `_prepare_clone`, `_execute_due_rows`) ensuring cyclomatic complexity $M \le 8$ (well under the $M \le 10$ gate) and nesting depth $< 4$.
- **Actor filtering**: Changes authored by the store/session identity (`_current_actor(store)`) are filtered before evaluating due table rows, mirroring the webhook-level machine account filter and preventing self-trigger loops.
