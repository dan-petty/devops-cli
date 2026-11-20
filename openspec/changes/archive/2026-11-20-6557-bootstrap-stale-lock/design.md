# Design

## Decisions

- The bootstrap never writes a tracked file. A step refuses a dirty worktree, and the bootstrap runs before the first step.
- One flag decides both lock rules: `locked` is true only for the new branch of a Planned item, which starts at the fetched default branch. Then uv runs `--locked` and npm runs `npm ci`, and both refuse a stale lock. Else uv runs `--frozen` and npm runs `npm install --no-save`, and both install the lock as it is.
- A stale lock of an existing branch stays for the agent. Its shell can run `uv lock` or `npm install` and commit the lock as part of its change.
- `--frozen` does not resolve. A seed that fits holds the packages of the same `uv.lock`, so the sync runs offline from the seed in both modes.

## Rejected alternatives

- Sync with no `--locked` or `--frozen`, and `npm install` with save: both write the lock again, and the step then stops on a dirty worktree.
- Commit the lock that the bootstrap writes: the Job would make a commit that no agent step asked for.
- Hash `pyproject.toml` into the seed too: #4814 builds the seed, and `--frozen` needs no such hash.
