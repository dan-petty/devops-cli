# Proposal: #4954

## Why

The stale-command check of the stage job (#3287) reads an ADDED requirement as the removal of a command when its text holds MUST NOT or SHALL NOT anywhere, and then counts each code span that starts with `devops ` or `--` as removed (#4954). A requirement that keeps a command and forbids one act of it becomes a removal. The plan of #2530 added "The command `devops pr check-readiness` SHALL read the changed files ... and MUST NOT request the pulls files list for them." The check read "`devops pr check-readiness` must not exist" and refused the plan with two stale-command problems. The stage job refused #2530 again on 2026-11-12 at 06:34Z (`stage gate returns: ... item=#2530 returns=3 result=refused`).

## What Changes

- `_removed_names` in `src/devops_cli/roadmap/stage/stage_change.py` counts a name as removed only when MUST NOT or SHALL NOT governs its code span. The span is the subject of the clause and the verb is exist or be available ("The `devops roadmap intake-eval` command MUST NOT exist."), or the span is the object of register, offer, list, accept, expose or provide ("MUST NOT register `devops roadmap intake-eval` as a command"). The subject can be a list of spans, and an option of a command ("The `--old` option of `devops x` MUST NOT exist.") removes the option only.
- A requirement that keeps a command and forbids one act of it removes nothing, so the stage job no longer refuses such a plan.
- The check still catches the removal that #3287 was filed for: the plan of #3185 wrote "MUST NOT register `devops roadmap intake-eval` as a command or as an alias".
- The spec delta adds the check requirement again. The archive of #4047 dropped the two #3287 requirements of the stale-command check from `openspec/specs/roadmap-stage/spec.md`. The delta adds "A base requirement that names a removed command is updated" with the new rule, and "The stale-command check reads the base requirement texts of its caller" as #3287 wrote it.
- The stage job refuses or accepts a plan by this check, which a consumer observes, so the change has a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: two ADDED requirements for the stale-command check.

## Impact

- `src/devops_cli/roadmap/stage/stage_change.py`: `_removed_names` and its patterns. `_REMOVAL_WORDS` goes.
- `tests/roadmap/stage/test_roadmap_stage_removal_references.py`: the cases of each form.
- The Service stages plans that forbid one act of a kept command, as #2530 did.

## Feasibility

- origin/main at `d64c897e2` holds the defect: `_removed_names` tests `any(words in text for words in _REMOVAL_WORDS)` on the full text and returns each `devops `/`--` span. The new tests give 6 failures on that commit, among them the two #2530 sentences.
- A scan of every `spec.md` under `openspec/` finds 83 requirement lines that the old rule reads as a removal. The new rule reads 82 of them as no removal, and none of the 82 removes a command or an option. It reads the one real removal, the #3185 line with `devops roadmap intake-eval`.
- `uv run devops roadmap eval stage --replay` gives the same result before and after the change: 58 cases, 82 judged defects, each gate catches each known defect, and 5 of 5 good plans pass.

## Existing Tool Considered

- spaCy can parse the subject and the object of a clause. It is not a dependency of the project, and its English model is a separate download. The Service image would get a large package and a model for one check. The #3287 design chose a small regular expression for this check, with no model call and no parser; this change keeps that design.
- Cost to build: about 60k tokens to build and test, about 5k tokens a year to keep and fix, and about 2 hours of elapsed time.
- Internal code deleted: `_REMOVAL_WORDS` and the test of a MUST NOT word on the full text.
