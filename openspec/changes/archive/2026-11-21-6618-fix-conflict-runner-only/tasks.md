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

## 2. Behavior: a round in a runner Job

- [x] 2.1 Step tests: a rebase that fails with no conflicted file stops the round and pushes nothing; the check before the push refuses a result that is no head branch, is the tip of main, does not hold main or lacks a change of the pull request; the clone commits as the bot on a host with no identity; a merge base 60 commits behind main is fetched; no merge base fails closed; the plan says what a confirmed round does; no `reference-transaction` hook of the clone runs
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py`
- [x] 2.2 `OriginGit` tests: a deepening that reaches the first commit makes the clone whole; a `reference-transaction` hook of the clone does not run
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py`
- [x] 2.3 The step and `OriginGit` do what the tests say, and the setting `roadmap.fix_conflict.tier2_mode` goes
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/roadmap/implement/test_roadmap_implement_git_isolation.py tests/security/test_config_declarations.py`

## 3. Documents

- [x] 3.1 The help of the command and of `--confirm` say that tier 1 and the push run only with `--confirm` in a runner Job, and the reference is generated again
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
