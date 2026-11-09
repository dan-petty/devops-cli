# Tasks

## 1. A reply that follows the prompt passes the schema

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 Add the tests: a plan with a reference of `unchanged: false` and `reason: null` validates, an unchanged reference with a null reason is refused, and a reply built from the `references` key of the prompt validates with `StageProposal`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 1.2 Type `StageReference.reason` as `Line | None` with the default `None`, and read it as `(ref.reason or "")` in the design file
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
