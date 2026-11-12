# Proposal: #4954

## Why

The stale-command check of the stage job (#3287) reads an ADDED requirement as the removal of a command when its text holds MUST NOT or SHALL NOT anywhere, and then counts each code span that starts with `devops ` or `--` as removed (#4954). A requirement that keeps a command and forbids one act of it becomes a removal. The plan of #2530 added "The command `devops pr check-readiness` SHALL read the changed files ... and MUST NOT request the pulls files list for them." The check read "`devops pr check-readiness` must not exist" and refused the plan with two stale-command problems. The stage job refused #2530 again on 2026-11-12 at 06:34Z (`stage gate returns: ... item=#2530 returns=3 result=refused`).

## What Changes

- `_removed_names` in `src/devops_cli/roadmap/stage/stage_change.py` counts a name as removed only when MUST NOT or SHALL NOT governs its code span. The span is in the subject of the clause, and the verb is exist, be available or the passive of a verb that offers a name ("The old `devops roadmap intake-eval` command MUST NOT exist.", "`devops roadmap intake-eval` MUST NOT be registered as a command."). Or the span is in the object of register, offer, list, accept, expose, provide, support, have or keep ("MUST NOT register or list the old `devops roadmap intake-eval` command"). The subject is the text from the start of the clause to the verb, so an article, an adjective, a trailing noun, bold marks or a closed parenthesis can be in it. A span after a preposition or after a word that starts a subordinate clause is not removed: "The `--old` option of `devops x` MUST NOT exist." removes the option only.
- The rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md` for a removed or renamed command tells the planner to state the removal in an added requirement with the sentence "`<old name>` MUST NOT exist.", the form that the check reads.
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

- `src/devops_cli/roadmap/stage/stage_change.py`: `_removed_names`, its phrase helpers and its patterns. `_REMOVAL_WORDS` goes.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md`: the removal sentence in the rule for a removed command.
- `tests/roadmap/stage/test_roadmap_stage_removal_references.py`: the cases of each form.
- `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`: the check reads the old name from the sentence of the prompt.
- The Service stages plans that forbid one act of a kept command, as #2530 did.

## Feasibility

- origin/main at `d64c897e2` holds the defect: `_removed_names` tests `any(words in text for words in _REMOVAL_WORDS)` on the full text and returns each `devops `/`--` span. `uv run devops ci fail-to-pass --base origin/main` gives 7 new cases that fail on that commit, among them the two #2530 sentences.
- A first version of the rule read only "The" or "Each", a noun and the span before the verb. A review sent 13 removals through it that the old rule caught and that it missed, such as "The old `devops roadmap intake-eval` command MUST NOT exist.", "`devops roadmap intake-eval` MUST NOT be registered as a command." and "`devops x` MUST NOT support `--old`.". The rule now reads the subject as the text from the start of the clause, and the tests hold each of these sentences.
- A scan of each line of every `spec.md` under `openspec/` that holds MUST NOT or SHALL NOT (714 lines) gives these counts of lines read as a removal: 157 for the old rule, 5 for the first version and 3 for this rule. The 3 lines are the #3185 removal of `devops roadmap intake-eval` (in its archive and in the living spec) and a scenario of this change. The two lines that the first version reads and this rule does not are scenario lines of this change, which the check does not read.
- `uv run devops roadmap eval stage --replay` gives the same result before and after the change: 58 cases, 82 judged defects, each gate catches each known defect, and 5 of 5 good plans pass.

## Existing Tool Considered

- spaCy can parse the subject and the object of a clause. It is not a dependency of the project, and its English model is a separate download. The Service image would get a large package and a model for one check. The #3287 design chose a small regular expression for this check, with no model call and no parser; this change keeps that design.
- Cost to build: about 120k tokens to build and test, with the review fix, about 5k tokens a year to keep and fix, and about 4 hours of elapsed time.
- Internal code deleted: `_REMOVAL_WORDS` and the test of a MUST NOT word on the full text.
