# Tasks

## 1. The token goes only to a git child that reaches a remote

Kind: behavior.

- [x] 1.1 Write failing tests: a `git push`, `git fetch` and `git ls-remote` child gets `GH_TOKEN`; a `git add`, `git commit` and `git diff` child gets none, also after the global options `-C` and `-c`; the guard accepts `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` and refuses any other value
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`
- [x] 1.2 Give the token only to a git child that reaches a remote, and accept the two fixed git keys
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`

## 2. A gh child reads the token from a private folder

Kind: behavior.

- [x] 2.1 Write failing tests: the environment of a gh child holds no `GH_TOKEN` and no `GITHUB_TOKEN`, `GH_CONFIG_DIR` names a 0700 folder with a 0600 `hosts.yml` that holds the token, and the folder is gone after a success, a failure and a timeout; the App's installation token takes the same path; with no `XDG_RUNTIME_DIR` the folder is under the data directory
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`
- [x] 2.2 Give a gh child a private configuration folder in place of `GH_TOKEN`
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/core/test_subprocess_env_boundary.py`
- [x] 2.3 Run `devops gh api` live: a filter of the environment finds no token, and a call that needs the token works
  - Verification: `$ uv run devops gh api user --jq .login`

## 3. The network git calls of the implement job

Kind: behavior.

- [x] 3.1 Write failing tests: with a hook folder, a credential helper and a GPG program in the home folder of the Job, a run pushes its branch and no program that a configuration file names sees the token; a call of `OriginGit` against a server that asks for Basic credentials asks no helper of the home folder or of the clone and uses no proxy of either; a pre-push hook does not run; the leftover processes end after the copy of the refs and before the call with the token
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_token_isolation.py tests/roadmap/implement/test_roadmap_implement_git_isolation.py`
- [x] 3.2 Add `roadmap/implement/git_isolation.py`, run each network call of the job through it, and give `add_worktree` its `origin`
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/git/test_worktree_add.py`

## 4. The settings check

Kind: behavior.

- [x] 4.1 Write failing tests: `filter.x.clean` with `* filter=x`, `gpg.program` with `commit.gpgsign`, and an extra `credential.helper` in the configuration of the clone each stop the item with the class `git_config` before the job runs git in the checkout again, and the log line holds the key and no value
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py tests/roadmap/test_roadmap_failure.py`
- [x] 4.2 Add the class `git_config` and the check, and run it when a turn of the agent ends and before each network call
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/test_roadmap_failure.py`

## 5. Documents

Kind: documents.

- [x] 5.1 Describe the invariants in SECURITY.md, docs/ROADMAP_WORKFLOW.md, `process_hardening.py` and `implement_run.py`
  - Verification: `$ uv run devops ci --check --only docs,openspec`

## 6. The review of the fix

Kind: behavior.

- [x] 6.1 Write failing tests: a verification command `git ls-remote --upload-pack=<probe> <remote>` starts no probe with the token, and `verification_problem` refuses each git form other than `! git grep`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_token_isolation.py tests/roadmap/implement/test_roadmap_implement_shell_policy.py`
- [x] 6.2 Refuse git in a verification command outside the negative search, and read each plan pull request head of the Service of the last 14 days before and after
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/test_roadmap_plan_read.py tests/roadmap/stage`
- [x] 6.3 Write failing tests: a refused setting ends the leftover processes before the check; a refused setting at a `wip:` push stops the item at once; a setting that an exit check writes gives the stop the class `git_config`; a fetch in a shallow clone gets the new commit
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py tests/roadmap/implement/test_roadmap_implement_wip_job.py`
- [x] 6.4 End the leftover processes before the check, stop the item on a refused setting at a push, and copy the `shallow` file
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py tests/roadmap/implement/test_roadmap_implement_wip_job.py`
- [x] 6.5 Write failing tests: in a runner the leftover processes end before each child with the token; a process that survives stops a gh call before its folder exists; the folder goes to the temp folder when the runtime folder fails, to an absolute data directory last, and never under a relative one; a cancelled async gh call leaves no folder
  - Verification: `$ uv run devops ci test tests/core/test_process.py`
- [x] 6.6 End the leftover processes before each child with the token in a runner, choose the folder with `platformdirs` and `tempfile`, and look up only the token in the thread of an async call
  - Verification: `$ uv run devops ci test tests/core tests/github`
- [x] 6.7 Describe the limits in SECURITY.md and docs/ROADMAP_WORKFLOW.md
  - Verification: `$ uv run devops ci --check --only docs,openspec`
- [x] 6.8 Write failing tests: a link at `<runtime folder>/devops-cli` does not move the gh folder; a runtime or temp folder in the current folder gets no gh folder; a token child that times out leaves no process of its group; in a runner the leftover processes end after each child with the token too; a link at `.git/shallow` stops the fetch; the write-back follows no link at a temporary name
  - Verification: `$ uv run devops ci test tests/core/test_process.py tests/roadmap/implement/test_roadmap_implement_git_isolation.py`
- [x] 6.9 Make the gh folder directly in the checked runtime folder and skip a candidate in the current folder; start each child with the token in a session of its own and kill its group on a timeout; sweep after the child in a runner; open `shallow` with `O_NOFOLLOW` and write it back with `mkstemp` and `os.replace`; correct the texts
  - Verification: `$ uv run devops ci test tests/core tests/github tests/roadmap/implement`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: run one implement Job in the cluster and read the push of its branch in the Job log.
