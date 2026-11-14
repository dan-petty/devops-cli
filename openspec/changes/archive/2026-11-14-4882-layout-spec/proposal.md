# Proposal

## Why

The requirement "Every caller imports a roadmap module by its path" names the test `test_every_import_of_a_roadmap_module_names_a_module_that_exists`. #4850 deleted that test, and its change set `skip_specs: true`, so the spec still names a check that no longer runs (#4882).

## What Changes

- A MODIFIED delta states the check that runs: mypy over `src/` and the pytest run over `tests/`.
- A `TYPE_CHECKING` import in `tests/` is out of scope, because mypy reads only `src/`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-package-layout`: The import requirement names the checks that run.

## Impact

- Spec: `openspec/specs/roadmap-package-layout/spec.md`

## Feasibility

- `TYPECHECK_PATHS = ("src",)` in `src/devops_cli/ci/typecheck.py`.
- `uv run devops ci test` collects and runs `tests/`.
- Verification commands: `uv run devops openspec check` and a read of the spec.

## Existing Tool Considered

mypy and pytest are the checks that the spec names. The change adds no code and no tool.
