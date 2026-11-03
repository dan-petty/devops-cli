# Tasks

## 1. Carry the reference hits in the stage reply

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_references.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_plan.py`, build a reply with a reference in a string literal under `tests/` and assert that the parsed `StageProposal` holds a `StageReference` for that path with its kind
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 Add `StageReference` with `path`, `kind`, `unchanged` and `reason` to `src/devops_cli/roadmap/stage_change.py`, and add the `references` list to `StageProposal` with an empty default
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Refuse an uncovered reference and render an unchanged one

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_content.py`, assert that `check_proposal` names a reference path that no group changes and that is not unchanged, that it returns no problem when a group changes that path, and that the rendered `design.md` holds the path and reason of an unchanged reference
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [ ] 2.2 Add the coverage check to `check_proposal` in `src/devops_cli/roadmap/stage_change.py`, with its message text beside the other stage problems, require a reason for an unchanged reference, and write each unchanged reference into `_design_file`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 3. Name the references and the verification in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Name the `references` tool on the old module path and its dotted name, a quoted target, a logger name and a snapshot file as references that an import rewrite misses, and ask a move plan for a `! git grep` check on the old dotted name over `src/` and `tests/`. Add the matching assertions to `tests/roadmap/test_roadmap_stage_prompt_rules.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
