# Task: Intake Never Closes as Duplicate an Item a Person Planned or Older Than Match (#1686)

**Issue**: [#1686](https://github.com/dan-petty/devops-cli/issues/1686)
**Scope**: scope/roadmap
**Feasibility**: Verified in-memory roadmap store and intake pipeline semantics: existing candidate items with milestones placed by a person (or set on GitHub) or with person-assigned Priority (via `priority/*` label or project card) are preserved and reported as possible duplicates left for a person, never closed automatically. Candidates older than their matched original are also held so the newer issue is closed instead of an older parent.

## Description
When `devops roadmap intake` processes candidates, an existing issue that a person planned (a milestone a person placed, or a Priority a person set on its card or label) must never be closed as a duplicate of another item. In particular, when an existing planned parent issue is split into smaller tasks, intake must not close the planned parent issue as a duplicate of one of its own splits. Furthermore, in a duplicate pair, intake must never close the older issue; if the model identifies a candidate that is older than the matched original, intake leaves both open and reports the pair as a possible duplicate held for a person.

Key changes:
- `src/devops_cli/config/constants.py`: Defined `CONST_ROADMAP_PRIORITY_LABEL_PREFIX = "priority/"`.
- `src/devops_cli/lang/en/messages.py`: Added `intake_possible_duplicate_line` template: `"- {subject}: possible duplicate of #{original}, left for a person: {reason}"`.
- `src/devops_cli/roadmap/intake.py`:
  - Added `held: bool = False` to `IntakeDecision`.
  - Added helpers `_has_person_milestone(subject)`, `_has_person_priority(subject)`, and `_is_planned_by_person(subject)` to check for person-planned milestones via `placed_by_person` and Priority set on card or `priority/*` label.
  - Updated `_duplicate(...)` to detect when `subject.number is not None` and (`_is_planned_by_person(subject) or subject.number < original`). In this case, `held=True` is returned with `quota=QuotaDecision.NOT_COUNTED`.
  - Updated `has_writes` and `writes()` to produce no writes when `held=True`.
  - Updated `_apply_decision(...)` to ensure no closure is performed when `decision.held` is true.
  - Updated `_decision_lines(...)` to format held candidates with `intake_possible_duplicate_line` and omit quota decision suffixes.

## Acceptance Criteria
- [x] **A candidate with a person-placed milestone is held as possible duplicate**: `test_a_candidate_with_a_person_placed_milestone_is_held_as_possible_duplicate` verifies that a candidate with a release placed by a person is not closed as a duplicate and no comment or board changes are written.
- [x] **A candidate with a person Priority is held as possible duplicate**: `test_a_candidate_with_a_person_priority_is_held_as_possible_duplicate` verifies that an issue with a `priority/*` label is preserved without closure.
- [x] **An older candidate matched to a newer original is held**: `test_a_candidate_older_than_its_matched_original_is_held_as_possible_duplicate` verifies that an older issue matched against a newer original is kept open.
- [x] **An unplanned newer candidate is closed as duplicate**: `test_an_unplanned_newer_candidate_matched_to_an_older_original_is_closed_as_duplicate` confirms that normal duplicate closure continues to operate on unplanned newer issues.
- [x] **Intake plan report**: `test_intake_plan_reports_possible_duplicate_left_for_a_person` checks that `devops roadmap intake --plan` reports held candidates as `possible duplicate of #{original}, left for a person: {reason}` with zero planned writes.
