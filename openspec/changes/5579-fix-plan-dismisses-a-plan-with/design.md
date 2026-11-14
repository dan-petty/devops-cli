# Design

## Decisions

- **Read both finding line forms, and take the part of an old place from its first word.**: Open stage comments predate #5418, so their lines are the only record of their findings. The old place names no part, and its first word names the part in each place of a real stage comment: `group`, `spec`, `criterion` and `decisions`.
- **A line that neither form reads ends the attempt as `unreadable_findings` before any model call, and the step posts no comment for it.**: A comment of this step that names the pull request becomes the newest plan comment, so the next attempt would read that comment in place of the stage comment and lose the lines. The result line and one log line for each unreadable line report them instead.
- **A plan is dismissed only when the review of the head and the last plan comment list no blocker or major finding.**: The review of the head missed the two blockers and five major findings of #5449, so a clean review alone dismissed a plan whose comment still listed open defects. The comment keeps the label now, and the attempt cap bounds the retries.
- **Hold every type that the pass may return in `OPEN_TYPES`, so the severity alone decides whether a finding is open.**: The type was a second blocking rule, and `other` fell through it. A second rule leaves the next new type with the same defect.
- **Give `JUDGE_OPEN_TYPES` an explicit literal of the four types that the review of refine opens.**: It is defined as `OPEN_TYPES` less three types, so widening `OPEN_TYPES` widens that review too and a major `other` finding would refuse a bot item, against the requirement of `roadmap-refine/review`. A literal keeps the two open sets apart.

## Rejected alternatives

- **Add `other` to `OPEN_TYPES` and keep the type as a second rule of the open set.**: A major `contrived_test` finding would stay advice, and the next type that the pass adds repeats the defect of #5449.
- **Widen `OPEN_TYPES` and leave `JUDGE_OPEN_TYPES` as a subtraction.**: `src/devops_cli/roadmap/refine/refine_judge.py:43:JUDGE_OPEN_TYPES: Final[frozenset[DefectType]] = OPEN_TYPES - {` follows the wider set, so a major `other` finding on a proposal of refine would refuse the item and contradict `openspec/specs/roadmap-refine/review/spec.md`.
- **Count the old-form lines as unreadable and leave the reader as it is.**: `src/devops_cli/roadmap/steps/fix_plan.py:356: if len(findings) < len(lines):` is the reader that dropped the three findings of #5449, so the plan would keep the label with no repair and no way forward.
- **Post one comment for an attempt that could not read a line, and list the lines there.**: `plan_comment` returns the newest comment that holds a plan marker and names the pull request, so that comment would replace the stage comment as the source of the findings.
- **Read both line forms and leave the dismissal rule as it is.**: `src/devops_cli/roadmap/steps/fix_plan.py:def _decide` reads only `revision.before`, so the three findings of #5449 would still end `dismissed`.
