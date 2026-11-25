# Proposal: #6198

## Why
Intake and retitle comments repeat text that the issue body, labels, or title already show: refine deferrals lack an `apart` set and trigger `Related: #<parent>` next to `Split from #<parent>`, `_reason_lines` emits `Related: #N` when the body already names `#N`, the Priority line copies the `priority/*` label value, and retitle comments write an `- After:` line repeating the new title set in the same run.

## What Changes
- Add `apart: Collection[int] = ()` to `NewCandidate` and populate it from refine deferrals (`item.number` plus `refine.deferred`) so `_apart` excludes them from the duplicate shortlist.
- Reuse a shared `#N` reference parser (`issue_references` in `body_hash.py`) across refine and intake so `_reason_lines` omits `Related: #N` when the body references `#N`, while keeping `Possible duplicate: #N`.
- Keep priority reasons and P0 granted/refused details in the Priority comment line without copying the `priority/*` label value.
- Remove `- After: \`{new}\`` from retitle change comments in `messages.py` and `retitle.py`.
- Add contract and behavior tests in `tests/roadmap/intake/` and `tests/roadmap/test_roadmap_retitle.py`.

## Capabilities
- `roadmap-intake-duplicates`
- `roadmap-intake-reason-comment`
- `roadmap-retitle`

## Impact
Users and maintainers reading intake and retitle comments get concise non-redundant facts while preserving duplicate flags (`Possible duplicate: #N`) and silent behavior when no lines remain.

## Feasibility
Confirmed on `origin/main`: `NewCandidate` (`intake.py:215`) has no `apart` field, `_deferral_candidate` (`refine.py:3943`) sets no `apart`, `_reason_lines` (`intake.py:1113`) writes `Related` and `priority[0]` unconditionally, and `retitle.py:428-446` passes `new=change.title` to templates with `- After:`.

## Existing Tool Considered
No open library extracts project-specific `#N` intake suppressions or retitle comment templates; the shared `#N` regex in `refine.py` is extracted into `body_hash.py` at an estimated 150 lines / 45k tokens build cost.
