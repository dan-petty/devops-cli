# Proposal: #6557

## Why

The coder bootstrap of #6517 (PR #6537) runs `uv sync` without `--locked` on an existing branch, so a stale `uv.lock` is locked again. But it still ran `npm ci --ignore-scripts` there, which refuses a `package-lock.json` that does not match `package.json`, and its uv-seed path synced offline whenever the sha256 of `uv.lock` fit the seed, which a stale lock can do; an offline sync cannot resolve. Closes #6557.

## What Changes

- On an existing branch (`locked` false), `bootstrap_checkout` runs `npm install --ignore-scripts`; the new branch of a Planned item keeps `npm ci`.
- The offline seed sync runs only with `--locked`. Without it, the seed fills the uv cache and the sync stays online.
- The spec scenario of a stale staged lock states the one sync that runs.

## Capabilities

- `roadmap-implement-runner`: MODIFIED requirements 'A Job builds the coder environment of its checkout' and 'The bootstrap uses the uv seed when it fits'.

## Impact

A staged branch or a fix-checks branch with a stale lock no longer stops at the step `bootstrap`. No new step, gate, retry or failure class.

## Feasibility

- `npm ci --ignore-scripts` exits 1 with `EUSAGE` when `package.json` holds a dependency that the lock lacks (npm 12).
- uv 0.13.9: `uv sync --group dev --offline` fails when `pyproject.toml` changed after the lock, with "the network was disabled".
- Two new tests in `tests/roadmap/test_roadmap_runner_tools.py` fail before the change and pass after it.

## Existing Tool Considered

npm and uv already give both modes (`npm ci` / `npm install`, `--locked` / unlocked, `--offline`). The change only chooses the mode by the existing `locked` flag.
