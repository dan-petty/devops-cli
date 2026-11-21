# Proposal

## Why

`devops repos worktrees add <issue> -r <clone of a private repo>` cannot read `origin`, so no agent can create a worktree there, and the run removes merged worktrees before that read fails. #6340 records the run of 2026-11-18 on the clone of a private repository and the behavior it expects: each git call of devops that reaches GitHub gets the credential of the session, and a run that cannot pass its preconditions changes nothing in the clone.

## What Changes

- `src/devops_cli/core/process.py` gains a helper that returns the two `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` for a git command that `git_reaches_remote` accepts, and nothing for any other command.
- `src/devops_cli/core/process.py` inserts those values at index 1 of the command in both runners, after the pin at `src/devops_cli/core/process.py:901:pin = _github_pin(full_cmd, env)` and `src/devops_cli/core/process.py:1035:pin = await asyncio.to_thread(_github_pin, full_cmd, env)`, so the dry-run branch at `src/devops_cli/core/process.py:879:if is_dry_run() and not (local_read or intent in ("read", "local_read")):` keeps its output.
- `src/devops_cli/infra/repo_tree.py` and `src/devops_cli/k8s/argocd_overrides.py` stop passing the `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` themselves, because the runner gives them to each git child that reaches a remote; a second copy would put each value twice in the argv.
- `src/devops_cli/git/worktree_add.py` gains a class that answers `heads` from one earlier read of the branches and runs `fetch` in the clone, so `add_worktree` keeps its signature and its one read at `src/devops_cli/git/worktree_add.py:535:heads = origin.heads()`.
- `src/devops_cli/git/worktree_add.py` names the failed git command without the inserted `-c` values, in the message of `src/devops_cli/git/worktree_add.py:245:MESSAGES.repos.worktrees_add_git_failed.format(`.
- `src/devops_cli/commands/repos.py` reads the branches of `origin` once before the reclaim at `src/devops_cli/commands/repos.py:914:reclaimed = reclaim_merged_worktrees(root, dry_run=is_plan) if reclaim else ReclaimResult()` and passes that read to `add_worktree`, so a failed read removes no worktree and leaves HEAD as it was.
- `tests/core/test_subprocess_env_boundary.py` adds the test of the helper and the test of a local git child, and updates the three assertions that compare the recorded argv of a network git child at `tests/core/test_subprocess_env_boundary.py:862:git_child = next(env for env in _child_envs(children) if env[0] == ["git", "fetch"])`.
- `tests/git/test_repos_worktrees_reclaim.py` adds the test of a failed read of `origin` on a clone that holds a merged worktree, built with `tests/git/test_repos_worktrees_reclaim.py:68:def _add(`.
- `docs/commands/repos.md` is regenerated from the new docstring of `worktrees add`, whose text at `docs/commands/repos.md:178:The command first removes the worktrees of merged pull requests under the agent worktrees` now says that the run reads `origin` before it reclaims.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: A git child that reaches a remote gets the GitHub credential helper, A git child that reaches no remote gets no credential helper
- `repos-worktrees-add`: The run reads origin before the reclaim

## Impact

- Code: `src/devops_cli/core/process.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/infra/repo_tree.py`, `src/devops_cli/k8s/argocd_overrides.py`
- Documents: `docs/commands/repos.md`
- Tests: `tests/core/test_subprocess_env_boundary.py`, `tests/git/test_repos_worktrees_reclaim.py`

## Feasibility

- The probes answer "The path `credential.https` is no file of the staging commit. No commit in the history deleted or renamed it.", so the two strings of the issue that look like paths are no file, and `read_file` of `src/devops_cli/core/process.py:448:def git_reaches_remote(args: Sequence[str]) -> bool:` gave the guard that decides which git child reaches a remote.
- `read_file` of the two runners showed that a git child gets the token alone and no `-c` value: `src/devops_cli/core/process.py:901:pin = _github_pin(full_cmd, env)` and `src/devops_cli/core/process.py:1035:pin = await asyncio.to_thread(_github_pin, full_cmd, env)`.
- The constant that the plan reuses is `src/devops_cli/config/constants.py:1214:CONST_GIT_GITHUB_CREDENTIAL_CONFIG: Final[tuple[str, ...]] = (`, whose two values name `credential.https://github.com.helper` and `!gh auth git-credential`, and the network subcommands are `src/devops_cli/config/constants.py:1229:CONST_GIT_NETWORK_SUBCOMMANDS: Final[frozenset[str]] = frozenset(`.
- `read_file` of `src/devops_cli/infra/repo_tree.py:60:*(word for value in CONST_GIT_GITHUB_CREDENTIAL_CONFIG for word in ("-c", value)),` showed the caller that passes the values itself, so the runner takes that work over, and the caller drops its copy so that no `-c` value appears twice in the argv of a child.
- `read_file` of `src/devops_cli/git/worktree_add.py:230:return _run([*self._git, "ls-remote", "--heads", CONST_GIT_REMOTE_ORIGIN, *branches])` showed the read of `origin` as one git child with no `-c` value, and `src/devops_cli/git/worktree_add.py:547:return _run([*_git(repo_root), "ls-remote", "--heads", CONST_GIT_REMOTE_ORIGIN])` is the reader of the branches that the command reuses.
- `read_file` of `src/devops_cli/git/worktree_add.py:534:origin = origin or _CloneOrigin(repo_root)` gave the parameter that `add_worktree` already takes, and `src/devops_cli/git/worktree_add.py:535:heads = origin.heads()` is its one read of the branches.
- `read_file` of `src/devops_cli/commands/repos.py:914:reclaimed = reclaim_merged_worktrees(root, dry_run=is_plan) if reclaim else ReclaimResult()` showed the reclaim before the call that reads `origin`, and `src/devops_cli/commands/repos.py:898:is_plan = dry_run or is_dry_run()` gave the guard that keeps a dry run off `origin`.
- `read_file` of `src/devops_cli/git/worktree_add.py:245:MESSAGES.repos.worktrees_add_git_failed.format(` showed the message that names the failed command from the words after the clone prefix, so the inserted `-c` values must be stripped there.
- The new helper needs no checkout, no client and no network: it reads the arguments of a command that the caller already built.
- `read_remote_heads` needs a checkout of the repository and a network to its `origin`; the test gives a clone in `tmp_path` whose `origin` is a path that does not exist, so the read reaches no network.
- `reclaim_merged_worktrees` needs a client of the GitHub API for its pull-request reads; the test gives a fake of the API, so no request leaves the process.
- `add_worktree` needs a checkout of the repository for its `git worktree add`; the test builds the clone in `tmp_path`.
- The verifies run `uv run devops ci test <path>` and `uv run devops ci --check --only docs`, which start `uv`, `python`, `pytest`, `git` and `gh` from the image; the image tools list holds each of them, so no program of the plan is `NOT_IN_RUNNER`. The failure classes are `test` for the two test verifies and `lint` for the docs row. The pod settings `readOnlyRootFilesystem: true` and `runAsNonRoot: true` apply: the tests write only into the temp folder of the pod, and the docs row writes no file.
- The first checks against the real system are `uv run devops ci test tests/core/test_subprocess_env_boundary.py`, `uv run devops ci test tests/git/test_repos_worktrees_reclaim.py`, `uv run devops ci --check --only docs` and `uv run devops ci fail-to-pass`, which shows the two new tests failing on the base commit.
- The detached HEAD of the clone on a successful run is not checked and stays out of scope: the code that the plan read detaches no HEAD of the clone, so the plan writes no code for it and states no test, and the open item #6354 holds it.

## Existing Tool Considered

The GitHub CLI `cli/cli` ships the credential helper `gh auth git-credential`, and the repository already uses it: the `Dockerfile` sets it as the system helper, the devcontainer sets it with `GIT_CONFIG_*` keys, and `devops infra` passed the `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG`. The alternatives block of the issue records the verdict `in-use`. The change reuses that helper in the process runner, so it builds no credential code and deletes no internal code.

## Dependencies

None.
