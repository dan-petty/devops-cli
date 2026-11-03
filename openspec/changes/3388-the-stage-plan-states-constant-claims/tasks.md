# Tasks

## 1. Add the claim entry and the reader of the staged values

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_probe.py`. Changes: `src/devops_cli/roadmap/stage_constants.py` (new), `tests/roadmap/test_roadmap_stage_constants.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_constants.py` first: a temporary git repository holds `src/devops_cli/roadmap/stage_change.py` with `BODY_MAX_CHARS: Final[int] = 800`, and `staged_constants` returns 800 for that name and no entry for a name that no module defines; `StageConstantClaim` refuses the name `BODY-MAX`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage_constants.py` with `StageConstantClaim` (an identifier `name` and an integer `value`) and `staged_constants`, which runs `git grep` for the name under `src/`, reads each file with `git show <commit>:<path>` and takes the value of a module-level literal with `ast.literal_eval`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` passes

## 2. Judge the claims in the plan check

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_constants.py`, `src/devops_cli/roadmap/stage.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Add to `tests/roadmap/test_roadmap_stage_plan.py` a test that a plan with a claim of 900 against the staged 800 gives one problem naming `BODY_MAX_CHARS` and `800`, a test that a claim of an undefined name gives one problem naming it, a test that a claim with the staged value gives no problem, and a test that `check_proposal` with no `constants` argument judges no claim
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Add `constant_claims: list[StageConstantClaim]` to `StageProposal`, add the keyword-only `constants` argument and the claim check to `check_proposal`, run the prose scan only when the list is empty, and pass the values that `staged_constants` read for the claimed names from the caller in `src/devops_cli/roadmap/stage.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. List the claim key in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add `constant_claims` to the reply keys of the prompt and one sentence that the plan lists each constant it relies on with its staged value; add the key to the prompt key test
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
