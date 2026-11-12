# Tasks

## 1. The token goes only to a git child that reaches a remote

Kind: behavior.

- [ ] 1.1 Write failing tests: a `git push`, `git fetch` and `git ls-remote` child gets `GH_TOKEN`; a `git add`, `git commit` and `git diff` child gets none, also after the global options `-C` and `-c`; the guard accepts `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` and refuses any other value
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`
- [ ] 1.2 Give the token only to a git child that reaches a remote, and accept the two fixed git keys
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`

## 2. A gh child reads the token from a private folder

Kind: behavior.

- [ ] 2.1 Write failing tests: the environment of a gh child holds no `GH_TOKEN` and no `GITHUB_TOKEN`, `GH_CONFIG_DIR` names a 0700 folder with a 0600 `hosts.yml` that holds the token, and the folder is gone after a success, a failure and a timeout; the App's installation token takes the same path; with no `XDG_RUNTIME_DIR` the folder is under the data directory
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`
- [ ] 2.2 Give a gh child a private configuration folder in place of `GH_TOKEN`
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`
- [ ] 2.3 Run `devops gh api` live: a filter of the environment finds no token, and a call that needs the token works
  - Verification: `$ uv run devops gh api user --jq .login`

## 3. The network git calls of the implement job

Kind: behavior.

- [ ] 3.1 Write failing tests: with a hook folder, a credential helper and a GPG program in the home folder of the Job, a run pushes its branch and no program that a configuration file names sees the token; a call of `OriginGit` against a server that asks for Basic credentials asks no helper of the home folder or of the clone and uses no proxy of either; a pre-push hook does not run; the leftover processes end after the copy of the refs and before the call with the token
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_token_isolation.py tests/roadmap/implement/test_roadmap_implement_git_isolation.py`
- [ ] 3.2 Add `roadmap/implement/git_isolation.py`, run each network call of the job through it, and give `add_worktree` its `origin`
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/git/test_worktree_add.py`

## 4. The settings check

Kind: behavior.

- [ ] 4.1 Write failing tests: `filter.x.clean` with `* filter=x`, `gpg.program` with `commit.gpgsign`, and an extra `credential.helper` in the configuration of the clone each stop the item with the class `git_config` before the job runs git in the checkout again, and the log line holds the key and no value
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py tests/roadmap/test_roadmap_failure.py`
- [ ] 4.2 Add the class `git_config` and the check, and run it when a turn of the agent ends and before each network call
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/test_roadmap_failure.py`

## 5. Documents

Kind: documents.

- [ ] 5.1 Describe the invariants in SECURITY.md, docs/ROADMAP_WORKFLOW.md, `process_hardening.py` and `implement_run.py`
  - Verification: `$ uv run devops ci --check --only docs,openspec`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: run one implement Job in the cluster and read the push of its branch in the Job log.
