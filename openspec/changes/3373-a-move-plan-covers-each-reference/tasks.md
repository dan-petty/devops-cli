# Tasks

## 1. Probe each reference of a moved module

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_references.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage_references.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_plan.py`, assert that reference_files returns every path of a `git grep` answer, with 70 files that hold one name and no cap; that the move derivation gives the old path and the dotted name of a module that a group moves and skips a test module and `conftest.py`; and that check_proposal refuses a probed path that no group changes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 Add reference_files to `src/devops_cli/roadmap/stage_references.py`, and the move derivation and the references argument of check_proposal to `src/devops_cli/roadmap/stage_change.py`. In `_settle` of `src/devops_cli/roadmap/stage.py`, probe the old path and the dotted name of each moved module after the reply, pass the hits to check_proposal, and probe them again for the groups that a split gives
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Refuse an uncovered reference and record an unchanged one

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_content.py`, assert that check_proposal names a probed path that no group changes and that is not unchanged, that it returns no problem when a group changes that path, that the schema refuses an unchanged reference with no reason, and that the rendered `design.md` holds the path, the kind and the reason of an unchanged reference
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [ ] 2.2 Add the reference coverage check to check_proposal in `src/devops_cli/roadmap/stage_change.py`, with its message texts in `src/devops_cli/lang/en/messages.py`, require a reason for an unchanged reference, and write each unchanged reference with its path, its kind and its reason into `_design_file`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 3. Name the references and the verification in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add a failing test to `tests/roadmap/test_roadmap_stage_prompt_rules.py` that reads the prompt and asserts the quoted target, the logger name, the snapshot file, the two `references` searches, the `! git grep` verification of a direct move, the dotted prefix of a prefix move, and the narrower search when the answer leaves files out
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 3.2 Name the two `references` searches, the three reference kinds, the `! git grep` verification of a direct move with the old dotted name, the old dotted prefix and the refused single-module literal of a prefix move, and the narrower search when the `references` answer leaves files out in `src/devops_cli/ai/tasks/roadmap_stage_change.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- The stage check does not compare `what_changes` with the group `changes`. Follow-up: #3411.
- The stage replay records no reference hit. Follow-up: #3412.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
