# Design

## Decisions

- **The process runner gives the credential helper to each git child that reaches a remote, in one place.**: One place covers `ls-remote` and `fetch --prune`, and no caller must remember the `-c` values.
- **A git command that already holds the `-c` values gets none again.**: `devops infra` and the Argo CD override fetch pass the values themselves, and their dry-run output and tests show them; the runner then adds no second copy, and a later change can move those two callers to the runner.
- **The runner inserts `-c <key>=<value>` at index 1 of the command, after it computes the pin from the command that the caller built.**: It reuses `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` and does not depend on the filtered `GIT_CONFIG_*` keys, and the guard `git_reaches_remote` reads the caller's own words.
- **`worktrees add` reads the branches of `origin` once before the reclaim and passes an object that answers `heads` from that read to `add_worktree`.**: A failed read changes nothing, a second read cannot fail after the removals, and `add_worktree` keeps the signature that its three callers already use.
- **The command reads `origin` before the reclaim only when it reclaims and is no dry run.**: A dry run makes no request to `origin`, and `--no-reclaim` keeps its order, where the local holder refuses the issue before any network read.
- **The message of a failed git read names the command without the `-c` values and the `-C <path>` prefix.**: The runner's values would otherwise land in the message of every failed network read of the module, and a person reads that message to find the failing command.
- **A git child that reaches no remote keeps its current behavior.**: The helper follows the same `git_reaches_remote` condition as the token, so a local git child gets neither the helper nor a token and starts no lookup.
- **The detached HEAD of the clone on a successful run stays out of scope and goes to #6354.**: The body records no code path that detaches HEAD, so the change can state no test and no fix; it stops before any change when the origin read fails.

## Rejected alternatives

- **Each caller passes the `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` to its own git call.**: The defect is two callers that forgot it, and a third caller can forget it again: `src/devops_cli/git/worktree_add.py:242:proc = run_subprocess(argv, check=False, quiet=True)` passes no value.
- **Set `GIT_CONFIG_COUNT` and `GIT_CONFIG_KEY_0` in the child environment.**: `build_subprocess_env` filters the environment, and the staged tree turns the git configuration files off: `src/devops_cli/config/constants.py:1224:{"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}`.
- **Keep the order of the command and make the reclaim undoable.**: A removed worktree cannot be restored, so the command would need more code and a record of each removal.
- **Investigate the detached HEAD of the clone in this change.**: The body records no code path that detaches HEAD, so the change can state no test and no fix for it; #6354 holds the investigation.

## Unchanged references

- `src/devops_cli/roadmap/implement/implement_run.py` (import): The plan keeps the signature of `add_worktree`: this caller passes no `origin`, so it keeps the clone's own reads.
- `src/devops_cli/roadmap/stage/stage.py` (import): The plan keeps the signature of `add_worktree`: this caller passes no `origin`, so it keeps the clone's own reads.
- `src/devops_cli/roadmap/steps/fix_checks_repair.py` (import): The plan keeps the signature of `add_worktree`: this caller passes no `origin`, so it keeps the clone's own reads.

## Security

The change gives each git child that reaches a remote the `gh auth git-credential` helper through `-c` values, so git sends the session's token to github.com only. The empty helper value clears every helper of the configuration files, so no other host sees a credential. The token still crosses the child boundary as `GH_TOKEN`, exactly as before. A person must confirm that the runner adds the values only for a command that `git_reaches_remote` accepts, and that a local git child still gets neither the helper nor a token. `test_a_local_git_child_gets_no_credential_helper` fails if that guard widens.
