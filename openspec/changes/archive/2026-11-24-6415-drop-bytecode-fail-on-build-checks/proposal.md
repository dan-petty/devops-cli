# Proposal: #6415

## Why
`.dockerignore` allows `src/**` without excluding Python bytecode. Local builds send unnecessary `__pycache__` folders and compiled files in the build context. The root Dockerfile also lacks `# check=error=true`, which lets build-check warnings go undetected. Closes #6415.

## What Changes
- Add `**/__pycache__`, `**/*.pyc`, and `**/*.pyo` to `.dockerignore` after `!src/**`.
- Add `# check=error=true` directly under the syntax directive in `Dockerfile`.
- Add invariant test assertions in `tests/invariants/test_service_image.py`.

## Capabilities
- Exclude bytecode from Docker build context.
- Treat Docker build-check warnings as fatal errors.

## Impact
- Build context size decreases for local Docker builds.
- New build-check warnings cause immediate build failure.

## Feasibility
Confirmed against real system. Dockerfile and .dockerignore changes pass image invariant tests and build check validation.

## Existing Tool Considered
BuildKit parser directives and standard .dockerignore pattern syntax are used directly.
