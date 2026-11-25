# Proposal: #7063

## Why

Runner Jobs (`cronjob-runner.yaml`), stage Jobs (`cronjob-stage.yaml`), and `planner-run` run outside `roadmap-service` without `DEVOPS_CLI_VALKEY_PASSWORD`, so their `publish` phase writes `status/in-review` and `implement.result="drafted"` directly to GitHub without updating `brain-issue` in `valkey-devops`.
Meanwhile, `webhooks.py` skips `_remember_delivery_issue` on `CONST_SERVICE_STATUS_OWN_WRITE` deliveries from the App bot, leaving stale `Status: In Progress` cached in Valkey for up to one hour (`DEFAULT_BRAIN_ISSUE_MAX_AGE_SECONDS = 3600`).
After `#6013`, `implement_submit._report` reads `_fresh(store, item.number)` through that stale Valkey entry, falsely treats the succeeded Job as a stop (`ci_infra`), posts a spurious stop comment, unlabels `owner/service` (which writes live `In Review` into Valkey), and then re-reads `_fresh` without re-checking `_settles_as_stop` before calling `write_status(StatusFacts(stopped=True))` — overwriting `status/in-review` with `status/blocked`. Closes #7063.

## What Changes

- Add `*, fresh: bool = False` to `item` and `issue` in `RoadmapStore`, `GitHubRoadmapStore`, and `InMemoryRoadmapStore`; when `fresh=True`, `GitHubRoadmapStore.issue` bypasses the 1-hour cache-hit shortcut, revalidates with `If-None-Match` if an `ETag` is cached or reads live GitHub otherwise, and refreshes `remember_issue` and `self._all`.
- Pass `fresh=True` in authoritative post-Job and read-back callers: `implement_submit._fresh`, `status_sync._read_back`, `stage_job.check_in`, `stage_job._return_for_split`, `fix_checks_row._record_unit`, and `stop_clear._clear_one`.
- Re-evaluate `_settles_as_stop` on the item passed to `write_status` inside `implement_submit._report` so releasing `owner/service` never overwrites a live non-stop outcome with `status/blocked`.
- Update `webhooks.py` so `own_write` `issues` deliveries refresh `brain-issue` when `payload.issue.updated_at` is strictly newer than the stored entry (or when no timestamp/entry exists), while still answering `ignored_own_write` (`self`) and waking no lane.
- Update step 25 of `docs/CLUSTER.md` to document `fresh=True` live reads and `own_write` issue cache refreshes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-brain/shared-cache`: Support `fresh=True` on `item` and `issue` so post-Job and read-back callers read live GitHub state past the 1-hour cache-hit window.
- `roadmap-implement-job/record`: Require `_report` to read live GitHub state (`fresh=True`) and keep `_settles_as_stop` consistent with the item written by `write_status`.
- `roadmap-service-webhooks`: Refresh `brain-issue` from newer `own_write` `issues` webhook payloads while keeping the `ignored_own_write` response and zero lane wakes.

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/fix_checks_row.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/server/routes/webhooks.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_github_store_brain.py`, `tests/server/routes/test_webhooks_brain.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`

## Feasibility

- Confirmed against cluster logs, GitHub event timelines (`#4416`, `#4649`, `#4650`, `#4709`), and manifests (`k8s/README.md:852`, `k8s/devops/cronjob-runner.yaml`, `k8s/devops/cronjob-stage.yaml`): Job pods run without `DEVOPS_CLI_VALKEY_PASSWORD`.
- Confirmed against `src/devops_cli/server/routes/webhooks.py:493-514, 718-735` (`refuse_own_write` prevents `_remember_delivery_issue`) and `src/devops_cli/roadmap/implement/implement_submit.py:359-402` (`_fresh` reads cached `store.item` and line 396 re-reads without re-checking `_settles_as_stop`).
- Offline tests verify all paths with `GitHubFake`, `shared_valkey`, `valkey_server`, and `RecordedGh`.

## Existing Tool Considered

Extends `RoadmapStore` and `roadmap_consumer` directly instead of granting runner Job pods Valkey network access and `DEVOPS_CLI_VALKEY_PASSWORD`, which `k8s/README.md` restricts to `deployment/roadmap-service`; estimated cost is ~40k tokens and 1 hour to implement and verify, with no external service or credential expansion needed.
