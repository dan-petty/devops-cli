# Tasks

## 1. The behaviors that stay (behavior)

- [x] 1.1 Add tests that `publish` refuses a changed link, a file that becomes a link and a link that becomes a file, and pushes nothing.
  - Verification: `$ uv run devops ci test tests/roadmap/phases/test_roadmap_phase_publish.py`
- [x] 1.2 Add tests that the withdraw of the review step deletes the branch with a lease, keeps a branch that another writer moved, and sends no push for a branch that is gone. Delete `OriginGit` and `git_isolation.py` with its tests, `GitSettingsError`, `link_shallow`, `CONST_GIT_TOKEN_CALL_CONFIG`, `CONST_GIT_SHALLOW_FILE` and `implement_git_settings_refused`, and make the withdraw a plain push in the clone.
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_review.py`

## 2. The token of a child (behavior)

- [x] 2.1 Change the tests of the process runner: each git child and each gh child gets the session's token as `GH_TOKEN` and no `GH_CONFIG_DIR`, a git child of the App stops when the mint fails, and a git child of a person with no login runs with no token. Change the tests of the implement job to the network calls: no helper and no `pre-push` hook that the agent planted runs, and a local commit runs the `pre-commit` hook.
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py tests/roadmap/implement/test_roadmap_implement_token_isolation.py`
- [x] 2.2 Delete `git_reaches_remote`, the private gh folder and its candidates, `_pinned`, the sweeps of the process runner, their constants and the four `gh_config_*` messages, and give each gh and git child `GH_TOKEN`.
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py tests/k8s/test_k8s_argocd_overrides.py tests/github`

- [x] 2.3 Add a test that a Ctrl+C during `git commit -a` with a slow `pre-commit` hook leaves no `.git/index.lock`, and send SIGINT to the group of a child of its own session before any SIGKILL.
  - Verification: `$ uv run devops ci test tests/core/test_process.py`
- [x] 2.4 Add a test that two git calls with no login start `gh auth token` once and that a gh call looks again, and keep a failed lookup for the git children.
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py`

## 3. The sweeps, the orphans and the link stop (refactor)

- [x] 3.1 Delete `adopt_orphans`, `end_leftover_processes`, each sweep of the agent phases, of a turn and of `publish_patch`, `implement_leftover_processes`, the autouse fixture of the sweep, the dependencies `psutil` and `types-psutil`, and their tests.
  - Verification: `$ ! git grep -n -e adopt_orphans -e end_leftover_processes -e implement_leftover_processes -- src/ tests/`
- [x] 3.2 Delete `_link_failure`, `implement_stop_link` and the test of the stop on a link.
  - Verification: `$ ! git grep -n -e _link_failure -e implement_stop_link -- src/ tests/`

## 4. The one container of the old runner template (behavior)

- [x] 4.1 Change the gate checks of the policy: a runner Job of one container and a Job with `envFrom` are refused on a `CREATE` and on an `UPDATE`. Delete the `UPDATE` branches of the one container and of `envFrom` from `admissionpolicy.yaml`.
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 4.2 Change the tests of the dry run of `run-job --template runner` to the create and the reads of the three containers alone, and delete the create and the reads of the one container `runner` from `dry_run_job`.
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_run_job.py`

## 5. Documents

- [x] 5.1 Describe the three containers and the token of each child in `SECURITY.md` item 15, `docs/ROADMAP_WORKFLOW.md` and `docs/CLUSTER.md`, and regenerate `docs/ERRORS.md`.
  - Verification: `$ uv run devops docs generate --check`
- [x] 5.2 Change the specs `subprocess-environment`, `roadmap-implement-runner`, `roadmap-implement-job/runner-job`, `roadmap-fix-checks`, `roadmap-fix-conflict`, `roadmap-implement-step/exit-checks`, `roadmap-phases`, `github-app-identity` and `gitops-host-overrides`.
  - Verification: `$ uv run devops ci --check --only openspec`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
