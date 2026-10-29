# Proposal

## Why

Issue #1119: the `actionlint-py` PyPI wrapper is stalled at version 1.7.12, which rejects `ubuntu-26.04` as an unknown label. The maintained upstream `actionlint` has reached v1.17.0, which accepts `ubuntu-26.04`. This change replaces the stalled PyPI wrapper with the maintained upstream binary, delivered as a digest-pinned Docker image so the gate never depends on a mutable PyPI release.

## What Changes

- The devcontainer `Dockerfile` adds a `FROM docker.io/kjanat/actionlint:1.17.0@sha256:d484ccca…` stage and `COPY --from` of the `actionlint` binary into the final image.
- `pyproject.toml` removes `actionlint-py` from the `dev` dependency group; `uv.lock` is regenerated.
- `src/devops_cli/commands/ci.py` changes the `actionlint` row's command from `["uv", "run", "actionlint"]` to `["actionlint"]`, and adds a `shutil.which` pre-check in the subcommand that exits with a clear message when the binary is not on `PATH` (skipped during `--dry-run`).
- `.github/workflows/ci.yml` adds a `docker://docker.io/kjanat/actionlint:1.17.0@sha256:d484ccca…` step to the `Static Analysis` job, and the gate now skips `actionlint` (it runs as a separate `uses:` step).
- `tests/test_ci.py`, `tests/test_ci_dry_run.py` and `tests/test_workflow_contracts.py` are updated to match the new invocation and to assert that the Dockerfile and CI workflow reference the same digest.
- `src/devops_cli/ai/knowledge_base/devops_cli/libraries/bandit_actionlint.md` and `python_packages.md` are updated to reflect the new invocation.

The change alters no observable behavior of `devops ci`: the `actionlint` row still runs the same linter against the same files, and the gate result is unchanged. It is a dependency and delivery-method refactor. `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The `actionlint` row of `devops ci` runs the same linter against the same files; only the binary's origin and invocation method change.

## Impact

- Code: `src/devops_cli/commands/ci.py` (CheckSpec command, `shutil.which` pre-check).
- Build: `.devcontainer/Dockerfile` (FROM + COPY stage).
- Config: `pyproject.toml` (remove `actionlint-py`), `uv.lock` (regenerated).
- CI: `.github/workflows/ci.yml` (docker:// step, skip list).
- Tests: `tests/test_ci.py`, `tests/test_ci_dry_run.py`, `tests/test_workflow_contracts.py`.
- Docs: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/bandit_actionlint.md`, `python_packages.md`.

## Feasibility

- `docker.io/kjanat/actionlint:1.17.0` exists on Docker Hub and its manifest is digest-addressable at `sha256:d484cccadf56b6a356466ade9af4c8e05c5dce1badaf0a9ecd0d7639d68d9c92`. The binary lives at `/usr/local/bin/actionlint` inside the image (confirmed via `docker inspect`).
- `actionlint` v1.17.0 accepts `ubuntu-26.04` as a valid label (upstream release notes), unblocking the lint gate.
- `COPY --from=image` is excluded from the COPY-coverage invariant in `tests/test_architectural_invariants.py:962-1000`, so the new COPY stage does not trip the ratchet.

## Existing Tool Considered

- `kjanat/actionlint` v1.17.0 is the upstream, actively maintained actionlint binary. Rather than continuing to depend on the stalled `actionlint-py` PyPI wrapper (last release 1.7.12), this change uses the upstream binary directly via a digest-pinned Docker image, which is the canonical distribution channel for the actionlint project.
- The change deletes the `actionlint-py==1.7.12.25` entry from `pyproject.toml` and the corresponding lock entry from `uv.lock`.
