### Problem Description

When the stage job returns an item to New at `CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT`, and the last failure is a degenerate reply (a placeholder in every text of the plan), the return comment shows the same problem two times.

`_Planner._stop_degenerate` in `src/devops_cli/roadmap/stage/stage.py` adds the degenerate reply with `MESSAGES.roadmap.stage_degenerate` to `self._refused`. It does not set `self._stopped_by_checks`. Then `_return_plan_defects` adds `failure.reason`, which is the same `stage_degenerate` text, after the refused problems. The result is two bullets that are the same.

PR #4537 (issue #4491) added this regression. Before #4537, `failure.problems or (reason,)` gave one bullet. The spec requirement in `openspec/specs/roadmap-stage/spec.md` says the comment gives the reason of the failure "unless the checks refused the last reply". The job keeps and logs the degenerate reply as a refused reply (`result=degenerate`), so the comment must not give its problem again.

The limit can occur on this path. `RoadmapStageDegenerateError` is a subclass of `RoadmapStageError`, so the failure class is `plan_defect` and it counts toward the limit. A degenerate reply repeats on the same body, because the same request gives the same reply.

### Reproduction Steps

1. Use a worktree at `origin/main` (after merge commit 9c666eac).
2. In `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`, add a round test: `_two_items(...)`, then `_fail_to_the_limit(store, 1, less=1)`. The plan answer for item 1 is `_placeholders()` from `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`. Run one round with `_run_stage_adapter`.
3. Assert that item 1 is New and that `_bullets(comment)` has no two bullets that are the same.

### Expected vs Actual Behavior

Expected: the return comment has one bullet for the degenerate reply.

Actual: the return comment has two bullets that are the same: `- Every text of the plan reply is a placeholder, such as `x` or `placeholder`. The same request gives the same reply, so the job sends no second request.` The assert `len(bullets) == len(set(bullets))` fails with `assert 2 == 1`.

### Environment Diagnostics

devops-cli `main` at 1936572f. Python test run with `uv run pytest`. No live system is necessary.

### Logs, Traces, or Terminal Output

```
>       assert len(bullets) == len(set(bullets))
E       AssertionError: assert 2 == 1
FAILED tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py::test_scratch_degenerate_reply_at_the_limit_gives_one_bullet
1 failed in 15.80s
```

### Proposed fix

Set `self._stopped_by_checks = True` in `_Planner._stop_degenerate` before the raise. The degenerate reply is a reply that the job refused and kept, and its problem is the failure reason. Add the round test above as the fail-to-pass test. The spec text needs no change.

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.


Source: https://github.com/dan-petty/devops-cli/pull/4537

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P3-Low", "Status": "In Review", "Value": "Low", "alternatives.failed_at": "2026-11-13T23:20:55.755452+00:00", "alternatives.failed_error": "AIClientError"} -->
