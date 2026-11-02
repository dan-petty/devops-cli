# Tasks

## 1. Measure the summary as the title shows it, and cut nothing

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `tests/support/builders.py`.

- [x] 1.1 Write failing tests: a title is refused, not cut, for a summary that does not fit and for a number of 7 digits; the schema refuses a summary with both counts and accepts spare whitespace; a summary over the limit goes back to the model with both counts and, refused twice, stops one item while the next is staged; the prompt says that a handle or a link costs characters
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 1.2 Give the limit to the JSON schema with `json_schema_extra`, count `safe_text(summary)` in the validator, make `staging_title` raise `RoadmapStageError` instead of cutting, and add the sentence to the prompt
  - Verification: `uv run devops ci test tests/roadmap`

## 2. Archive the change

Kind: other. Changes: `openspec/changes/3249-title-limit-followup`, `openspec/specs/roadmap-stage/spec.md`.

- [x] 2.1 Archive the change after every task is ticked
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- `delivery_title` and the "why" of `implement_run.py` still cut text with `...`, and a summary of a plan that ends with `...` passes the schema. Issue #3215 removes the cuts, and the open plan for #3200 refuses cut text in a plan.
- The first-reply refusal rate with a live model is not measured. Run `devops roadmap eval stage` once with the live model.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
