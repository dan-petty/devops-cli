# Design

## Decisions

- The bootstrap never writes a tracked file. A step refuses a dirty worktree, and the bootstrap runs before the first step.
- One flag decides both lock rules: `locked` is true only for the new branch of a Planned item, which starts at the fetched default branch. Then uv runs `--locked` and npm runs `npm ci`, and both refuse a stale lock. Else uv runs `--frozen`, which installs `uv.lock` as it is, and npm runs `npm install --no-save`, which installs the dependencies of `package.json` and writes no lock.
- A stale lock of an existing branch stays for the agent. Its shell can run `uv lock` or `npm install` and commit the lock as part of its change.
- No command of the Job before the first step writes a tracked file. The install of the hook environments runs right after the bootstrap, so `pre_commit_command` starts `pre-commit` with `uv run --frozen`. The per-step hook stages use the same command, so `uv` locks nothing there either. A hook of the repository that runs a plain `uv run` can still lock, as at a commit of a person.
- `--frozen` does not resolve, and `--locked` resolves only to refuse a stale lock. A seed that fits holds the packages of the same `uv.lock`, so the sync runs offline from the seed in both modes.

## Rejected alternatives

- Sync with no `--locked` or `--frozen`, and `npm install` with save: both write the lock again, and the step then stops on a dirty worktree.
- Commit the lock that the bootstrap writes: the Job would make a commit that no agent step asked for.
- Hash `pyproject.toml` into the seed too: #4814 builds the seed, and `--frozen` needs no such hash.
- `uv run --no-sync` for `pre-commit`: it also locks nothing, but it does not install a lock that the agent changed in a step. `--frozen` installs `uv.lock` as it is.
- `UV_FROZEN=1` in the environment of the hooks: it also gets to each hook. A hook that runs `uv lock` then only checks that the lock is valid and writes nothing (uv 0.13.9), so a hook of the repository could not update the lock.
