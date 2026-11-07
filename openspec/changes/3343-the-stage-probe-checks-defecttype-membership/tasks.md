# Tasks

## 1. Refuse a finding type outside DefectType

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_plan.py`, write `test_a_finding_kind_outside_defect_type_is_refused`, which passes a proposal whose group test text says `kind: placeholder` to `content_problems` and expects one problem that names `placeholder` and each member of `DefectType`. Add `test_a_finding_kind_inside_defect_type_passes`, `test_a_mapped_classification_to_other_passes`, `test_an_other_group_kind_is_no_finding_type` and `test_a_qualified_defect_type_outside_the_members_is_refused`, which expects a problem that names `PLACEHOLDER`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 Add `_FINDING_TYPES` and a helper `finding_type_problems(proposal)` to `src/devops_cli/roadmap/stage_change.py`. The helper collects the free text of the proposal: `summary`, `why`, each group `title`, `test`, `implementation` and `documentation`, each spec delta requirement `name`, `text` and scenario texts, each criterion text and `pull_request_body`. It skips `reads`, `changes`, `creates` and `kind`. It matches a `DefectType.` reference anywhere. It also matches a backticked `kind` or `type` and its value, only in a sentence that holds the word `finding` or `defect`, with `_one_line` applied first. A value that is not a member of `DefectType` gives a problem from `MESSAGES.roadmap.stage_problem_finding_type`, which names the value, lists the members and says to add the enum member or map the classification to `DefectType.OTHER`. Call the helper from `content_problems` and append its problems to the returned list
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
- [ ] 1.3 Add `stage_problem_finding_type` to `class RoadmapMessages` in `src/devops_cli/lang/en/messages.py`. The text takes the value and the members of `DefectType`, names the value and lists the members, and says to add the enum member or map the classification to `DefectType.OTHER`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## Criteria

- Group 1: A test asserts that a plan proposing an unlisted finding defect type without updating `DefectType` is refused.
- Group 1: A plan referencing valid `DefectType` members passes validation.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
