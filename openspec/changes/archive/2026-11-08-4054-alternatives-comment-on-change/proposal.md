# Proposal

## Why

A recheck of the alternatives job posts a comment, also when the verdict and the tool are the same as in the last check (#4054). The job checks an item again every `roadmap.alternatives.recheck_days` (30 by default). The comment thread of a long-lived item then fills with the same text, and a person cannot see when a check found something new.

## What Changes

- `AlternativesWriter.settle` posts the comment of a check only when the check is a first one, or when its verdict or its tool differs from the recorded `alternatives.verdict` and `alternatives.tool`. The item that the check read holds the record in `item.job_record`. A tool of `None` and a tool with a URL count as different.
- A check always writes the block and the marks with the one request of #4049. The date (`alternatives.checked_at`) moves, so the item is not due again before the recheck days pass. The race guard `_unchanged_since_read` and the order rule of #2951 stay.
- A check that posts no comment still emits `devops_cli_roadmap_alternatives_total` and `devops_cli_roadmap_alternatives_searches`, and the writer still counts it in `written`: the metrics and the count are of checks, not of comments.
- The reason, the searches and the sources of a recheck with the same result are not written. The block keeps the latest date and the tool facts.
- Refine and the alternatives job read `replies_after_marker` from the last comment of the job. With no new comment, the older comment stays the anchor, so a reply of a person after it is still read.
- The dry-run plan lists the comment with a new condition, `check_changed`: the check is a first one, or its verdict or its tool differs from the record. A dry run makes no request, so it cannot know which case an item is.
- The change carries a spec delta: the writes of a check, and the dry-run plan, are observable. It modifies the requirements "A check writes a comment, a block and a record" and "A check writes its block and its marks with one request" of `roadmap-alternatives`.
- The text "A check posts one comment and a body block" in the help of `devops roadmap alternatives`, in `README.md` and in `docs/roadmap/alternatives.md` is wrong after the change, so the change fixes it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: A check posts its comment only for a first check or a changed result.

## Impact

- Code: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/alternatives.md`, `README.md` (generated)
- Tests: `tests/roadmap/test_roadmap_alternatives_recheck.py` (new), `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_alternatives_one_write.py`
- Settings: none. The change adds, removes, renames and tightens no setting, and `recheck_days` is the same. It does not touch `k8s/devops/configmap.example.yaml` or the live ConfigMap. The key-walk test of #4093 (`tests/config/test_k8s_devops_runtime.py`) already loads the example ConfigMap into `Settings`, so the change needs no new test of it.
- Behavior a person sees: a recheck with the same result posts no comment, so the thread shows only the first check and each change.

## Feasibility

Checked on 2026-11-08 at origin/main `7935fbaa`, by reading the code and by running the new tests on the base.

- The issue names `apply_alternatives`. That name is gone: #4034 moved the writes to `AlternativesWriter.settle`, and #4049 (merged as #4130) made its write one request. The premise holds on `settle`: it always calls `set_marks(..., body=outcome.new_body)`, then `store.comment(number, outcome.comment)`, and it never compares the result with the record.
- The two values to compare are at hand. `AlternativesRecordKey.VERDICT` and `AlternativesRecordKey.TOOL` are in `outcome.item.job_record`, as read when the round took the item. The new values are `outcome.verdict.value` and `outcome.tool.url if outcome.tool else None`, the same values that `settle` writes as marks. No new read and no new mark is needed.
- The defect is real on the base. `uv run devops ci fail-to-pass --base origin/main` runs `tests/roadmap/test_roadmap_alternatives_recheck.py` and the new dry-run test. On the base, a recheck with the same verdict and tool posts a second comment (2 comments, 1 expected), and its writes are `set_marks` and `comment` (only `set_marks` expected). The run output path is in the state note of the stage.
- `test_first_check_posts_its_comment` and `test_changed_*` pin behavior that the base already has, so they pass on the base. The issue says that each command fails on the unchanged code. That is true of `same_verdict` only, and the others guard the new condition against a change that drops the comment of a changed check.
- The other readers of the comment marker are `alternatives.py` (`replies_after_marker`) and `refine.py`. They take the last comment with the marker as the anchor. With no new comment, the older one stays the anchor, so a person's reply after it is still read.
- No merged pull request, open pull request or newer issue or ADR does this work. The pull requests that touch `alternatives.py` (#4080, #4101, #4130) change other code.

## Existing Tool Considered

The marks of the item record (`alternatives.verdict`, `alternatives.tool`) already hold what the compare needs, and the writer already has the new values. No library is needed, and the change adds no dependency. It adds one compare and one condition, and deletes no code. Cost: about 15k tokens and 1 hour to write, about 1k tokens a quarter to keep, and about 5k tokens and 0.3 hours to fix.
