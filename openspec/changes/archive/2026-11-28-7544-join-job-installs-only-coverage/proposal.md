# Proposal

## Why

The required check `Tests & Coverage` averages about 362 s against the limit of 360 s (AGENTS.md rule 5). Its time is the slowest test shard plus the join job `Tests & Coverage`. The join job runs only coverage and diff-cover. But its step `Set up uv toolchain` ran a full `uv sync` of every group and extra with a bytecode compile, and took 21 s to 31 s (#7544).

## What Changes

- A new dependency group `coverage` of `pyproject.toml` holds coverage and diff-cover at the versions of `uv.lock`. The `dev` group includes it, so a local `uv sync` and the images install the same tools.
- The composite action `setup-toolchain` gets the input `dependency-group`. With it, the sync installs only that group, with no project.
- The join job installs only the group `coverage`, with no bytecode compile and no tooling cache, and sets `UV_NO_SYNC` so that no `uv run` of the job syncs more.
- The job keeps its name, its steps, its artifact, the floor `fail_under = 85` and the changed-line floor `--fail-under 90`.
- `docs/SDLC.md` names the group.
- The change alters a CI workflow, a CI action and a development group. A consumer of devops-cli observes no change, so the change has no spec delta (`skip_specs: true`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Workflows: `.github/workflows/ci.yml` (job `test`), `.github/actions/setup-toolchain/action.yml`.
- Dependencies: `pyproject.toml`, `uv.lock` (group metadata only; no version changes).
- Documents: `docs/SDLC.md`.
- The change fits one pull request.

## Feasibility

- In the log of the join job of run 46103047841, setup-uv took 4.6 s. Then the sync logged `Prepared 270 packages in 2.74s`, `Installed 270 packages in 1.29s` and `Bytecode compiled 25395 files in 20.15s`. The step also restored the tooling cache `.mypy_cache` and `.ruff_cache`, and no step of the job reads it.
- In the last 5 push runs of `main` (46103047841, 46102488879, 46102127064, 46098309980, 46098277385), the join job took 42 s to 61 s. `Set up uv toolchain` took 21 s to 31 s of it.
- In the last 6 pull request runs (46105289209, 46101545593, 46100851878, 46099763476, 46097479479, 46096319310), the join job took 70 s to 83 s. `Set up uv toolchain` took 25 s to 31 s of it.
- With uv 0.13.10, `uv sync --locked --only-group coverage` installed 7 packages and no project. From that environment, `coverage combine`, `coverage report` (exit 2 under `fail_under = 85`), `coverage xml` and `diff-cover --fail-under 90` ran on the coverage data of a local test run. `UV_NO_SYNC=1` stops `uv run` from a sync and does not change `uv sync`.
- `uv lock` changed only the group metadata of `uv.lock`: coverage stays 7.17.5, and diff-cover stays 11.0.5.

## Existing Tool Considered

- uv dependency groups (PEP 735) and `uv sync --only-group` hold the pins in `pyproject.toml` and `uv.lock`, where Renovate updates them. The change adds no installer and no copy of a pin.
- The change deletes no internal code.
