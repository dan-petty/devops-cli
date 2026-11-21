# Tasks

## 1. Behavior

- [x] 1.1 Step tests: without `confirm` the step returns `planned` and runs no `uv`; with `confirm`, a hook or a setting that tier 1 writes into the clone changes no push; a fetch reads no setting of the clone; no local git call runs a hook; in a runner Job a refused setting stops the push
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py`
- [x] 1.2 Command tests: `--confirm` outside a runner Job runs no step; in a runner Job the command calls the runner check and the two process guards before the step
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_fix_conflict.py`
- [x] 1.3 The step reads the URL of `origin` after its clone, fetches and pushes through `OriginGit`, turns the hooks off for each local git call, and rebases only with `confirm`; the command accepts `--confirm` only in a runner Job
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/commands/test_roadmap_step_fix_conflict.py`
- [x] 1.4 Step tests: in a runner Job, a docs and lockfile round on the shallow clone of the step checks out the head branch, continues the rebase, generates both files again and pushes, and no git call of the step sets an environment variable; a generation that fails in the rebase of the implement job returns false and records the stop
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py`
- [x] 1.5 `git rebase --continue` takes `-c core.editor=true` and no environment override
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py`

## 2. Documents

- [x] 2.1 The help of the command and of `--confirm` say that tier 1 and the push run only with `--confirm` in a runner Job, and the reference is generated again
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
