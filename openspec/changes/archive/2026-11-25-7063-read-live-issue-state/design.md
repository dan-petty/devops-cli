# Design

## Decisions

- **Add an explicit `fresh: bool = False` keyword parameter to `RoadmapStore.item` and `RoadmapStore.issue`.**: Keeping `fresh=False` as the default preserves 1-hour cache hits for normal listing/read paths while allowing callers that must observe out-of-process Job writes or read back Service mutations (`implement_submit._fresh`, `status_sync._read_back`, `stage_job.check_in`, `stage_job._return_for_split`, `fix_checks_row._record_unit`, `stop_clear._clear_one`) to request live state.
- **Revalidate cached `ETag` entries even when `fresh=True`.**: When `fresh=True` and `cached` has an `ETag`, `GitHubRoadmapStore.issue` uses `_revalidate_issue` (`If-None-Match`), saving primary GitHub rate limit on unchanged issues (`304`) while immediately detecting external writes (`200`). When `etag` is absent (for example webhook-populated entries), `fresh=True` performs a direct `issue_args` read.
- **Re-check `_settles_as_stop` on the item returned by `_fresh` right before `write_status` in `implement_submit._report`.**: Even if a Job finishes between the log-tail read and `service_release`, evaluating `_settles_as_stop` against the exact refreshed `Item` passed into `write_status` prevents `status/blocked` from overwriting `status/in-review`.
- **Refresh `brain-issue` on newer `own_write` `issues` webhook payloads inside `refuse_own_write`.**: Only `issues` events (`payload.comment is None`, `payload.issue is not None`, `payload.issue.pull_request is None`) update `brain-issue`, and only when `payload.issue.updated_at > existing.record.updated_at` (or no timestamp/entry exists). Strict inequality avoids letting same-second delayed webhooks overwrite newer `PATCH` states and `ETag`s written by `_kept`, while still returning `CONST_SERVICE_STATUS_OWN_WRITE` and queuing no lane work.

## Rejected alternatives

- **Give runner and stage Job pods `DEVOPS_CLI_VALKEY_PASSWORD` to write to `valkey-devops`.**: `k8s/README.md` deliberately omits Valkey credentials from Job pods so agent-executing workloads cannot mutate shared Service cache keys, and network/outage fallbacks would still require `fresh=True` in `_report` and webhook updates anyway.
- **Call `issue_cache(repo).pop(str(n), None)` before reads in callers.**: Deleting the key discards the cached `ETag`, preventing `304 Not Modified` conditional reads and forcing an unconditional GitHub API request on every check.
