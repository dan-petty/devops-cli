# Tasks

## 1. Behavior

- [x] 1.1 Command tests: `--confirm` outside a runner Job runs no step; in a runner Job the command calls the runner check and the two process guards before the step
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_fix_conflict.py`
- [x] 1.2 Step tests: the plan runs no code; the push goes to the URL that the step read; an archive commit that is not the tip; an archive commit that holds code; a spec commit that is no archive commit; an archive commit whose generated document conflicts too; a generated document that main deleted; a git call that fails; a docs and lockfile round with no environment override; a renamed file; a merge of main; a `uv.lock` version line in plan and round; a failed rebase; no commit past main; the tip of the implement branch after a failed round
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py`
- [x] 1.3 The command gates `--confirm`, and the step does what the tests say; the setting `roadmap.fix_conflict.tier2_mode` goes
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/commands/test_roadmap_step_fix_conflict.py tests/security/test_config_declarations.py`

## 2. Documents

- [x] 2.1 The help of the command and of `--confirm`, the generated reference, and the lines of ADR 0021
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
