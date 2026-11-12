# Tasks

## 1. A removal names the command that MUST NOT governs

- [x] 1.1 Add the cases of `tests/roadmap/stage/test_roadmap_stage_removal_references.py`: the #2530 sentences and other sentences that forbid one act of a kept command give no problem, and each removal form (subject with exist, be available or a passive, a subject with an adjective, a trailing noun, bold marks or a closed parenthesis, a list of subjects, a list after a colon, a second clause, the object of register, list, accept, support, have or keep, an object with an adjective, two verbs of one object, an option of a command) gives one problem that names the removed name. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`
- [x] 1.2 Change `_removed_names` in `src/devops_cli/roadmap/stage/stage_change.py` to read the subject form and the object form, and delete `_REMOVAL_WORDS`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py tests/roadmap/stage/test_roadmap_stage_content.py`
- [x] 1.3 Add the removal sentence "`<old name>` MUST NOT exist." to the rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md` for a removed command, and test in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` that the check reads the old name from it.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## 2. Replay of the stage gates

- [x] 2.1 Run the stage replay on the base and on the change, and compare the gate rows and the good plans.
  - Verification: `$ uv run devops roadmap eval stage --replay`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
