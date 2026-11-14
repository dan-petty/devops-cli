# Tasks

## 1. Keep the head on the item branch when a push rebase conflicts

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/git_isolation.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [ ] 1.1 `tests/roadmap/implement/test_roadmap_implement_job.py` `test_a_conflict_at_a_checkpoint_keeps_the_later_group_on_the_branch` fails on the base: the conflicting checkpoint pushes nothing, so the branch on `origin` holds no commit of group 2 and the record holds no `implement.conflict`; the test moves `main` over `CONTEXT.md` after group 1 passes. `tests/roadmap/implement/test_roadmap_implement_push_current.py` `test_a_conflict_at_a_wip_push_keeps_the_wip_commit_on_the_branch` replaces `test_a_conflict_at_a_wip_push_and_at_the_stop_pushes_nothing`, which asserts the old rule
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py tests/roadmap/implement/test_roadmap_implement_job.py` fails on the base
- [ ] 1.2 Write both tests first. In `_push_passed`, catch a `_StopError` whose `failure_class` is `FailureClass.CONFLICT` and call a new `_push_head_after_conflict`: it stores the files on the run, writes `implement.conflict` with `self.store.set_marks`, prints the conflict to stderr with `print_muted`, pushes the head with `_push_with_lease`, or with `_publish` when the item has no pull request yet, and returns the empty text, so `_checkpoint` keeps its checkpoints and a stop adds the kept-work note. A push that fails there returns the failure note, as before, and a `_StopError` that is not a conflict keeps its old result. In `stop`, write `stop.conflict_files or self.conflict_files` to `implement.conflict`. Update the docstrings of `_push_passed`, `_checkpoint`, `_current_tip` and `_rebase`. Rename the old test and assert that the branch on `origin` holds the `wip:` commit and that `implement.conflict` names the conflicting file. In `tests/roadmap/implement/test_roadmap_implement_job.py`, parametrize the `staged_tasks` fixture to a three-group tasks text whose group 1 changes `CONTEXT.md`, add `advance_main` of `CONTEXT.md` with other text as the effect after group 1's reply, and assert that the branch on `origin` holds the commit of group 2, that `implement.conflict` names `CONTEXT.md`, and that the stop class is `conflict`. Then run `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`: the final-push conflict tests, `test_a_conflict_on_the_rebase_before_the_push_pushes_nothing` and `test_a_conflict_on_the_rebase_before_the_push_names_the_conflicted_files`, keep their assertions and pass
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py tests/roadmap/implement/test_roadmap_implement_job.py` passes

## 2. State the conflict push rule in the docs

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`, `src/devops_cli/roadmap/implement/implement_run.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`.

- [ ] 2.1 In the Checkpoints bullet of `docs/ROADMAP_WORKFLOW.md`, replace the sentence that a rebase conflict pushes nothing (#4670) and the sentence that a checkpoint that fails goes to the log with the new rule: a conflict at a checkpoint, a `wip:` push or a stop push aborts the rebase, pushes the head with a lease, records the conflict and its files, and the Job keeps its checkpoints; the final push keeps the pushed branch and stops the Item with the class `conflict` and the conflicting files. In the Current Branch at Every Push bullet of `docs/SDLC.md`, replace the clause that the implement Job pushes nothing after a rebase conflict with the same rule
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `docs/ROADMAP_WORKFLOW.md` and `docs/SDLC.md` to state that a conflict push keeps the passed work on the item branch
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
