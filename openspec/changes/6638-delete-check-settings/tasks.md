# Tasks

## 1. The tests of the network call (tests)

- [x] 1.1 Add tests that an `insteadOf`, a `pushInsteadOf` and a `pushurl` of the home folder and of the clone get no request, and that a `pre-push` hook in the hooks folder of the clone does not run.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py`

## 2. The deletion of the scan (refactor)

- [x] 2.1 Change the tests of the `git_config` stop paths and of the sweep before a refusal to a link at the `shallow` file (`link_shallow`), and delete the tests that cover only the scan.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py tests/roadmap/implement/test_roadmap_implement_checkpoint.py tests/roadmap/test_roadmap_faults.py tests/roadmap/test_roadmap_failure.py`
- [x] 2.2 Delete `check_settings`, `refused_settings`, their helpers and constants, the message `implement_git_attribute_refused`, the scan after a turn in `implement_step.py`, the second sweep of `OriginGit` and the `isolated` option of `_git`. Change the texts of `GitSettingsError`, `git_config` and `implement_run.py` to the `shallow` file.
  - Verification: `$ ! git grep -n -E "refused_settings|check_settings\(|CONST_GIT_ALLOWED_SETTING|CONST_GIT_ATTRIBUTE_|CONST_GIT_BUILTIN_DRIVERS|CONST_GIT_ALTERNATES_FILE|implement_git_attribute_refused" src/ tests/`

## 3. Documents

- [x] 3.1 Remove the scan from `SECURITY.md` and `docs/ROADMAP_WORKFLOW.md`, and regenerate `docs/ERRORS.md`.
  - Verification: `$ uv run devops docs generate --check`
- [x] 3.2 Change the spec `roadmap-implement-runner`: remove the requirement of the scan, and change the requirements of the sweeps, of the checkpoint and stop push, and of the network call.
  - Verification: `$ uv run devops ci --check --only openspec`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
