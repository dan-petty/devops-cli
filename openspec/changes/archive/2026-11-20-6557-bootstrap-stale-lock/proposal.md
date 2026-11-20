# Proposal: #6557

## Why

The coder bootstrap of #6517 (PR #6537) runs `uv sync` with no `--locked` on an existing branch. On a stale `uv.lock`, that sync locks again and writes `uv.lock`. The bootstrap also runs `npm ci --ignore-scripts` there, which refuses a `package-lock.json` that does not match `package.json`. Both locks are tracked files. After the bootstrap, the step refuses a dirty worktree (`_require_clean`), so fix-checks returns no fix and the implement Job stops at group 1 before its first model request. Closes #6557.

## What Changes

- On an existing branch (`locked` false), `bootstrap_checkout` runs `uv sync --frozen --group dev` and `npm install --no-save --ignore-scripts`. Both install the lock as it is and write no tracked file. The new branch of a Planned item keeps `--locked` and `npm ci`.
- A stale lock of an existing branch is the work of the agent: its shell can run `uv lock` or `npm install` and commit the lock.
- `--frozen` does not resolve, so a seed that fits makes the sync offline in both modes, as before #6557.

## Capabilities

- `roadmap-implement-runner`: MODIFIED requirements 'A Job builds the coder environment of its checkout' and 'The bootstrap uses the uv seed when it fits'.

## Impact

A staged branch or a fix-checks branch with a stale lock no longer stops at the step `bootstrap` or at the clean-worktree check of its first step. No new step, gate, retry or failure class.

## Feasibility

- `npm ci --ignore-scripts` exits 1 with `EUSAGE` when `package.json` holds a dependency that the lock lacks (npm 12).
- uv 0.13.9: `uv sync --group dev` with no `--locked` or `--frozen` writes a stale `uv.lock` again. `uv sync --help` gives `--frozen` as "Sync without updating the `uv.lock` file".
- npm 12.2.2 (`@npmcli/config` definitions): `save` false "will also prevent writing to `package-lock.json`".
- A scratch repository with a stale `uv.lock` and a stale `package-lock.json`, both committed: `bootstrap_checkout(path, locked=False)` passes and `git status --porcelain` is empty.

## Existing Tool Considered

uv and npm already give both modes (`--locked` / `--frozen`, `npm ci` / `npm install --no-save`, `--offline`). The change only chooses the mode by the existing `locked` flag.
