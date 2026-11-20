# Proposal: #6557

## Why

The coder bootstrap of #6517 (PR #6537) runs `uv sync` with no `--locked` on an existing branch. On a stale `uv.lock`, that sync locks again and writes `uv.lock`. The bootstrap also runs `npm ci --ignore-scripts` there, which refuses a `package-lock.json` that does not match `package.json`. Both locks are tracked files. After the bootstrap, the step refuses a dirty worktree (`_require_clean`), so fix-checks returns no fix and the implement Job stops at group 1 before its first model request. Closes #6557.

## What Changes

- On an existing branch (`locked` false), `bootstrap_checkout` runs `uv sync --frozen --group dev` and `npm install --no-save --ignore-scripts`. uv installs `uv.lock` as it is. npm installs the dependencies of `package.json`, uses the lock where it fits and writes no lock, so on a stale `package-lock.json` the Node tree can hold packages that the lock does not name. Neither command writes a tracked file. The new branch of a Planned item keeps `--locked` and `npm ci`.
- The Job starts each `pre-commit` command with `uv run --frozen` (`pre_commit_command`). Both callers install the hook environments right after the bootstrap, and a plain `uv run` locks a stale `uv.lock` again and writes it.
- A stale lock of an existing branch is the work of the agent: its shell can run `uv lock` or `npm install` and commit the lock.
- `--frozen` does not resolve, and `--locked` resolves only to refuse a stale lock. A seed that fits makes the sync offline in both modes, as before #6557.

## Capabilities

- `roadmap-implement-runner`: MODIFIED requirements 'A Job builds the coder environment of its checkout' and 'The bootstrap uses the uv seed when it fits'. ADDED requirement 'The hook commands of a Job lock nothing'.

## Impact

A staged branch or a fix-checks branch with a stale lock no longer stops at the step `bootstrap` or at the clean-worktree check of its first step. The steps run the same hooks, as `uv run --frozen pre-commit`. No new step, gate, retry or failure class.

## Feasibility

- `npm ci --ignore-scripts` exits 1 with `EUSAGE` when `package.json` holds a dependency that the lock lacks (npm 12).
- uv 0.13.9: `uv sync --group dev` with no `--locked` or `--frozen` writes a stale `uv.lock` again. `uv sync --help` gives `--frozen` as "Sync without updating the `uv.lock` file".
- npm 12.2.2 (`@npmcli/config` definitions): `save` false "will also prevent writing to `package-lock.json`".
- A scratch repository with a stale `uv.lock` and a stale `package-lock.json`, both committed: `bootstrap_checkout(path, locked=False)` passes and `git status --porcelain` is empty.
- uv 0.13.9, a scratch repository with a stale `uv.lock`: after `uv sync --frozen`, `uv run --frozen python -c pass` leaves `git status --porcelain` empty, and `uv run python -c pass` gives ` M uv.lock`. `uv run --help` gives `--frozen` as "Run without updating the `uv.lock` file".
- uv 0.13.9: `uv sync --locked --offline` on a stale lock that names a package outside the cache fails with "No solution found when resolving dependencies", so `--locked` resolves.

## Existing Tool Considered

uv and npm already give both modes (`--locked` / `--frozen`, `npm ci` / `npm install --no-save`, `--offline`). The change only chooses the mode by the existing `locked` flag.
