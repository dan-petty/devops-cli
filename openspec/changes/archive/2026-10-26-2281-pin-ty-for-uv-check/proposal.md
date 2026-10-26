# Proposal

## Why

Issue #2281: `uv run devops ci` failed the `uv check` step on a clean `main`.
`ty` v0.0.92 reported a `redundant-cast` warning in `src/devops_cli/ai/tools/__init__.py`, and the step treats a warning as a failure.
No change in the repository caused the failure. The file did not change, and the `ty` version was not pinned.
`uv check` downloaded the newest `ty` in its default range at run time, so a new `ty` release can fail `main` again at any time.

## What Changes

- Pin `ty==0.0.92` in the `dev` dependency group of `pyproject.toml`, and lock it in `uv.lock`.
  `uv check` then uses the exact version in `uv.lock`, as the other gate tools (`ruff`, `mypy`, `bandit`, `zizmor`) already do.
- Add a row for `ty` to the pinned-tool table of the knowledge base.
- Add an offline test that the `dev` group pins `ty` and that `uv.lock` holds the same version.
- The redundant `cast` needs no edit. Pull request #2283 replaced it with `fn: Any = self.function`, and `uv check` passes on `main` with `ty` v0.0.92.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: none.
- Configuration: `pyproject.toml`, `uv.lock`.
- Tests: `tests/test_ci.py`.
- Documentation: `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`.

## Feasibility

- Command output on `main` at 7f1145a4, `uv` 0.12.23: `uv check` exited 1 with one `redundant-cast` diagnostic at `src/devops_cli/ai/tools/__init__.py:126`.
- `uv check --ty-version 0.0.91` passed on the same tree, so the new `ty` release is the cause.
- `uv help check` documents the `--ty-version` option: "By default, the exact version resolved in `uv.lock` will be used when `ty` is a project dependency or a dependency in the project's `dev` group. Otherwise, a constrained version range of ty will be used (e.g., `>=0.0,<0.1`)."
- After the pin, `uv check -v` logs `Identified uncached distribution: ty==0.0.92` and the step passes. `uv lock --check` passes.
- On `origin/main` at ad7c38b1, `uv check` already passed with `ty` v0.0.92, because #2283 changed the cast line. This change therefore makes no edit to that file.

## Existing Tool Considered

`uv check` has the pin built in: a `ty` entry in the `dev` group. No new code and no `--ty-version` option in `devops ci` is necessary.
The internal code that the change deletes: none.
