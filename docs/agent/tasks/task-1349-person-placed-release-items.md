# Task: An item a person places in a release stays there, and the roadmap jobs comment on a rule it breaks instead of moving it out (#1349)

**Issue**: [#1349](https://github.com/dan-petty/devops-cli/issues/1349)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: type/fix, scope/roadmap, priority/p1-high

## Description

Before this change, when a person moved an item into a started release or a cut release, the roadmap reprioritize job moved it out (to the backlog or the next release) on the subsequent poll or run. Furthermore, intake did not preserve candidate milestones if the issue already had a milestone assigned by a person.

The owner established that a person's placement in a release stands: the item stays in that release, and the roadmap jobs comment on the rule it breaks instead of moving it out.

- **Admission override for person-placed items**:
  - In `reprioritize.py`, `admission_decision` checks if the item was placed by a person (`person=placed_by_person(...)`).
  - If placed by a person and the state is not `merged` (as clarified by the owner, a merged release whose PR is in `main` is locked so code can no longer ship in it), a non-admit transition becomes `Transition(Action.ADMIT, transition.reason)` with `joined=True`.
  - The job posts a comment detailing the rule bypassed (admission, p0_feature, or cut).
  - Later runs do not post duplicate comments because a distinct mark `JobMark.JOINED = "Joined"` records the release milestone number.
- **Cap calculations**:
  - Person-joined items are excluded from cap displacement decisions in `_cap_decisions`.
- **Intake preservation**:
  - In `intake.py:_placement`, when `subject.release is not None`, the candidate's milestone is preserved rather than overwritten.
- **Store-level verification**:
  - In `memory_store.py` and `github_store.py`, `set_field(ItemField.RELEASE, ...)` verifies that the item's current milestone on GitHub matches before updating, raising `RoadmapCardChangedError` if changed concurrently.

## Acceptance Criteria

- [x] When a person places an item in a started release, it stays there and is admitted (`Action.ADMIT`) with a comment explaining the bypassed rule (`test_a_feature_placed_by_a_person_after_the_start_stays_in_the_release` and related tests in `tests/test_roadmap_reprioritize.py`).
- [x] When a person places a non-critical item in a cut release (whose PR is open), it stays there and is admitted with a comment (`test_a_feature_placed_by_a_person_in_a_cut_release_stays_in_the_release`).
- [x] A person's placement is not protected once a release is `merged` (`ReleaseState.MERGED`), sending critical fixes to the next release as required by #1294 (`test_a_person_placed_critical_fix_in_merged_release_goes_to_next`).
- [x] Subsequent runs do not post duplicate comments for person-joined items, tracked via `JobMark.JOINED` (`test_a_person_placed_item_does_not_get_duplicate_comments_on_subsequent_runs`).
- [x] Person-joined items are excluded from cap calculations, not displacing other items or being descoped by the cap (`test_person_joined_items_are_excluded_from_cap_decisions`).
- [x] `devops roadmap intake` preserves candidate milestones when already set (`test_candidate_with_milestone_preserves_release` in `tests/test_roadmap_intake.py`).
- [x] Store implementations verify milestone state before write and raise `RoadmapCardChangedError` if changed (`test_placing_an_item_in_a_release_checks_milestone_first` in `tests/test_roadmap_store_contract.py`).
- [x] Hypothesis state machine and lifecycle properties pass with person-placed items admitted and tracked (`tests/test_roadmap_lifecycle_properties.py`).
- [x] Changelog fragment `changelog.d/1349.md` records the deliverable.

## Deliverables

- [x] `src/devops_cli/roadmap/reprioritize.py`: `admission_decision` person override, `_cap_decisions` exclusion of person-joined items, `_final_marks`, `_admits`, `joined_release`.
- [x] `src/devops_cli/roadmap/store.py`: `JobMark.JOINED`, `release_number`.
- [x] `src/devops_cli/roadmap/intake.py`: candidate milestone preservation in `_placement`.
- [x] `src/devops_cli/roadmap/memory_store.py` & `src/devops_cli/roadmap/github_store.py`: pre-write milestone check raising `RoadmapCardChangedError`.
- [x] `CONTEXT.md`: updated Current release and Reprioritization definitions.
- [x] `changelog.d/1349.md`: changelog entry for #1349.
- [x] Tests: `tests/test_roadmap_reprioritize.py`, `tests/test_roadmap_intake.py`, `tests/test_roadmap_store_contract.py`, `tests/test_roadmap_github_store.py`, `tests/test_roadmap_lifecycle_properties.py`.
