# Tasks

## 1. A removal names the command that MUST NOT governs

- [x] 1.1 Add the cases of `tests/roadmap/stage/test_roadmap_stage_removal_references.py`: the #2530 sentences and other sentences that forbid one act of a kept command give no problem, and each removal form (subject with exist or be available, a list of subjects, a second clause, the object of register or list, an option of a command, the object of accept) gives one problem that names the removed name. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`
- [x] 1.2 Change `_removed_names` in `src/devops_cli/roadmap/stage/stage_change.py` to read the subject form and the object form, and delete `_REMOVAL_WORDS`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py tests/roadmap/stage/test_roadmap_stage_content.py`

## 2. Replay of the stage gates

- [x] 2.1 Run the stage replay on the base and on the change, and compare the gate rows and the good plans.
  - Verification: `$ uv run devops roadmap eval stage --replay`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
