# Proposal

## Why

Issue #2554 reports that devops sandbox deploy fails with a raw Docker API 404 error when the sandbox image is not on the local engine. The first deploy on a fresh engine always fails because no code pulls the image before creating the container. The default image is python:3.14-slim.

## What Changes

- Add a pull_image method to DockerEngineService that checks for the image locally and pulls it only when absent.
- Update the DockerEngineFake to support images.get and images.pull for test coverage.
- Call pull_image from WorkloadSandboxRunner.run before create_container.
- Raise a DockerEngineError that names the image reference and the failure reason when a pull fails.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `sandbox-deploy`: pull-missing-image-before-container-creation, skip-pull-when-image-exists-locally, name-image-in-pull-failure-error

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py`, `src/devops_cli/docker/sandbox.py`
- Tests: `tests/support/fakes/docker_engine.py`

## Feasibility

- The premise is confirmed: src/devops_cli/docker/sandbox.py calls engine.create_container in WorkloadSandboxRunner.run with no prior image pull. src/devops_cli/docker/engine.py has no pull_image method. The default image python:3.14-slim is set in devops_cli.config.defaults (DEFAULT_SANDBOX_IMAGE).
- The docker SDK (docker-py 7.2.0) already provides client.images.get(name) and client.images.pull(repository, tag). The project already depends on it. No new library is introduced.
- First check: run uv run devops sandbox deploy --name check --network-mode isolated on an engine without python:3.14-slim to confirm the 404. Second check: run uv run devops ci test tests/docker/test_engine_pull_image.py to verify the new pull_image method. Third check: run uv run devops ci test tests/docker/test_sandbox_deploy_pull.py to verify the deploy path calls pull before create.

## Existing Tool Considered

docker-py (v7.2.0, already a project dependency) provides client.images.pull(repository, tag) and client.images.get(name). The project wraps the SDK through DockerEngineService but does not call either method in the sandbox deploy path. The fix adds one pull_image method to DockerEngineService and calls it from the sandbox deploy code. No new library is introduced.
