# Proposal

## Why

`check_proposal` in `src/devops_cli/roadmap/stage_change.py` judges a plan's shape, paths and spec delta, and never the finding types that the plan names. A plan can therefore propose `kind: placeholder`, which is not a member of `DefectType` (`src/devops_cli/roadmap/stage_eval_cases.py`). The mistake surfaces only when the verification pass refuses a `Finding` whose `type` is outside the enum (`src/devops_cli/roadmap/stage_verify.py`, #3343).

## What Changes

- Add a finding-type rule to `content_problems` in `src/devops_cli/roadmap/stage_change.py`, which both `check_proposal` and the replay call, that reads the free text of a plan and refuses a finding type outside `DefectType`.
- Add the problem text `stage_problem_finding_type` to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`: it names the value and lists the members of `DefectType`.
- Scan only the free text: summary, why, group titles and task texts, spec delta texts, criteria texts and the pull request body.
- Ignore paths, `reads`, `changes`, `creates` and the structured group `kind`, so an `other` group is no finding type.
- Report a problem that names the value, lists the members of `DefectType` and asks for the enum member or a mapping to `DefectType.OTHER`.
- Add tests in `tests/roadmap/test_roadmap_stage_plan.py` for an unknown `kind:`, a known `kind:`, a mapped classification and an unknown `DefectType.` reference.
- Add a requirement to the `roadmap-stage` capability, because the stage job's check of a plan is behavior a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A finding type in a plan is a member of DefectType

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`

## Feasibility

- `probes` confirms the cited files: "The path `src/devops_cli/roadmap/stage_verify.py` is a file of the staging commit.", "The path `src/devops_cli/roadmap/stage_eval_cases.py` is a file of the staging commit.", "The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_stage_plan.py` is a file of the staging commit."
- `probes` shows no member path and no `DefectType.OTHER` path, which is expected: enum members are not files, and `stage_eval_cases.py` defines `OTHER = "other"` in `DefectType`.
- `read_file` of `src/devops_cli/roadmap/stage_change.py` shows `content_problems` and its helpers (`_one_line`, `StageProposal`), so the rule joins the check that the stage job and the replay already call on every plan.
- `read_file` of `src/devops_cli/lang/en/messages.py` shows `class RoadmapMessages`, where the new problem text joins the other stage problem texts.
- `read_file` of `tests/roadmap/test_roadmap_stage_plan.py` shows the unit tests of `check_proposal`, such as `test_a_spec_delta_goes_with_an_observable_change`, so a new rule is proved offline in the same file.
- `read_file` of `src/devops_cli/roadmap/stage_verify.py` shows `class Finding` with the field `type` typed `DefectType`, which is the field that a plan's finding-type value must satisfy.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py`.

## Existing Tool Considered

No open, maintained tool or library checks the prose of a plan against an enum of a repository. Pydantic validates `Finding.type` at runtime, after the plan is written, and it cannot see the plan text. The project builds the staging rule itself: about 8,000 tokens to build, about 2,000 tokens to keep and fix, and about 4 hours elapsed. No internal code is deleted.
