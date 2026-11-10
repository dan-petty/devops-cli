# Tasks

## 1. The implement job pushes a branch that holds the default branch

Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py` (new), `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/support/roadmap_implement.py`.

- [x] 1.1 Write `tests/roadmap/implement/test_roadmap_implement_push_current.py` and two cases in `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`: `main` gains a commit, and the first `wip:` push, a later `wip:` push, the checkpoint and the push of a stop each hold it. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py`
- [x] 1.2 Add `_current_tip`, `_rebased_copy`, `_refspec` and `_move_wip` to `implement_run.py`, give `_rebase` its checkout, and make `_push_passed` push the current tip
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py`

## 2. The stage job pushes a plan branch that holds the default branch

Reads: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`.

- [x] 2.1 Change the stage test of the staged commit and add a conflict case: the branch holds the commit that `main` gained, and a conflict pushes nothing. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_apply.py`
- [x] 2.2 Add `_rebase_onto_default` to `stage.py` and call it in `_commit_and_push`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_apply.py`

## 3. Documents

Reads: `src/devops_cli/roadmap/implement/implement_run.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stage/stage.py`.

- [x] 3.1 Update the module text of `implement_run.py` and the comments of `stage.py` that say the branch starts at the staged commit
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: A push of the implement job holds the commit that `main` gained.
- Group 2: A plan branch holds the commit that `main` gained.
