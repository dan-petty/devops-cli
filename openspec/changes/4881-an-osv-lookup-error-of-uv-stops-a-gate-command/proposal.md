# Proposal: #4881

## Why

A short DNS failure of `api.osv.dev` stops a gate command. `pyproject.toml` turns on uv's
`malware-check` preview feature, and the devcontainer sets `UV_MALWARE_CHECK=1`, so `uv run` asks
`api.osv.dev` before it starts a program. Twice on 2026-11-11/12 in the devcontainer, a busy host
could not resolve that name, and uv stopped with `error: Malware check failed due to an error from
OSV ... failed to lookup address information: Try again`. The stop came before the program started:
`uv run devops ci test <files>` stopped before pytest, and the `ast-grep scan` pre-commit hook
failed, so `git commit` failed. The same command passed a minute later. Closes #4881.

## What Changes

- The check-only rows of `devops ci`, the `pre-commit` hooks that start `uv run`, and the interactive
  shell configurations set `UV_MALWARE_CHECK` to `0`, so a lookup error cannot stop a row or a hook
  that installs no package.
- The steps that install packages keep `UV_MALWARE_CHECK` at `1`: the `Synchronize dependencies`
  step of `.github/actions/setup-toolchain/action.yml` and the `postCreateCommand` of the
  devcontainer and its template.
- `pyproject.toml` records beside `[tool.uv]` that uv has no setting that turns an OSV lookup error
  into a warning or lengthens the retry, and the uv knowledge base records the split.

## Capabilities

`uv-malware-check` (new): where the malware check of uv is on and where it is off.

## Impact

- A short OSV lookup failure no longer stops a gate row, a commit or a push.
- The check still runs where a package can arrive: an install step keeps `UV_MALWARE_CHECK=1`.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: uv 0.13.9 has no documented setting that downgrades an OSV lookup error to a
  warning or lengthens its retry, and an already-synced `uv run` still asks OSV before it starts the
  program (`uv --help`, `pyproject.toml:328`). The repository already uses `UV_MALWARE_CHECK` as the
  switch: `.devcontainer/image/devcontainer.json:46` and `.claude/settings.json:14` set it to `1`.
- `UV_MALWARE_CHECK` matches the `UV_` allowed prefix of `build_subprocess_env`, so a caller may set
  it to `0` for a child without a refusal (`src/devops_cli/core/process.py:139`).

## Existing Tool Considered

uv (astral-sh/uv, Apache-2.0, maintained, already in use) runs the OSV malware check and exposes the
`UV_MALWARE_CHECK` switch. It lacks a documented setting that turns an OSV lookup error into a
warning and a way to lengthen the retry, so an already-synced `uv run` still aborts. No other tool
covers the need.
