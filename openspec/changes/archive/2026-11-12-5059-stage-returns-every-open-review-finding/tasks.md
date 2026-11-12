# Tasks

## 1. Return each open finding to the planner

Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/refine/refine_judge.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/roadmap/round_log.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`.

- [x] 1.1 Write the tests first in `tests/roadmap/stage/test_roadmap_stage_verification.py`: a quoted `criterion_dropped` finding, a quoted `spec_delta_wrong` finding and a placeholder finding each give the planner a second request that names the finding in `problem`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verification.py`
- [x] 1.2 Merge `RETURN_TYPES` into `OPEN_TYPES`, delete `returning`, start a repair round in `StageJob._verified` when the review has an open finding, and count the open findings in `devops roadmap eval verify`. Update the tests of `tests/roadmap/stage/test_roadmap_stage_verify.py` that read `RETURN_TYPES` and `returning`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verification.py tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/roadmap/refine/test_roadmap_refine_trust.py`

## 2. Tell the planner how to fix each open type

Reads: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 2.1 Write the test first in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`: the text that explains `problem` names the open findings of a model review, `criterion_dropped` and `spec_delta_wrong`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 2.2 Add the fix of each type to the first paragraph of `src/devops_cli/ai/tasks/roadmap_stage_change.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## 3. Documents

- [x] 3.1 State in `docs/roadmap/stage.md` that each open finding returns the plan
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
