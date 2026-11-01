## Problem Description

`devops sandbox deploy` fails when the sandbox image is not on the local engine. It does not pull the image, and the error is the raw Docker API reply. The default image is `python:3.14-slim`, so the first deploy on a fresh engine fails.

`DockerEngineService` creates the container with `containers.create` (`src/devops_cli/docker/engine.py`), and no code under `src/devops_cli/sandbox/` or `src/devops_cli/docker/` pulls an image first.

## Reproduction Steps

1. Make sure the engine has no `python:3.14-slim` image.
2. Run `uv run devops sandbox deploy --name check --network-mode isolated`.

## Expected vs Actual Behavior

- Expected: the command pulls the image (or, if the design refuses pulls, stops with a message that names the image and the command that pulls it), then deploys.
- Actual: `✗ Failed deploying sandbox: Failed deploying sandbox container: Container creation failed: 404 Client Error for http+docker://localhost/v1.56/containers/create: Not Found ("No such image: python:3.14-slim")`, exit 1.

## Environment Diagnostics

- devops-cli on origin/main d156ce7e (2026-10-28).
- Docker Engine 29.9.2, docker SDK 7.2.0.

## Logs, Traces, or Terminal Output

After `docker pull python:3.14-slim`, the same deploy works, and `devops sandbox logs` returns stdout and stderr apart (#2520).

## Existing Tool Considered

The docker SDK has `images.pull`, and `containers.run` pulls a missing image itself. Nothing new is built.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
`devops sandbox deploy` fails with a raw Docker API 404 error when the sandbox image is not on the local engine. The command does not pull the image before it creates the container. The first deploy on a fresh engine always fails. The default image is python:3.14-slim.

### Acceptance criteria

### Requirement: Pull missing image before container creation
When the sandbox image is not present on the local engine, the deploy command SHALL pull the image before it creates the container.

#### Scenario: Deploy with a missing image
- **WHEN** The engine has no image matching the sandbox image reference
- **THEN** The command pulls the image and then creates the container without a 404 error

### Requirement: Skip pull when image exists locally
When the sandbox image is already present on the local engine, the deploy command SHALL NOT issue a registry pull request.

#### Scenario: Deploy with an existing image
- **WHEN** The engine already has an image matching the sandbox image reference
- **THEN** The command creates the container without a network pull call

### Requirement: Name the image in a pull failure error
When the image pull fails, the error message SHALL contain the image reference and the reason for the failure.

#### Scenario: Pull fails due to a registry error
- **WHEN** The image pull fails because the registry is unreachable or the image does not exist in the registry
- **THEN** The error message contains the image reference and the failure reason

### Existing Tool Considered
docker-py (v7.2.0, already a project dependency) provides `client.images.pull(repository, tag)` to pull an image and `client.images.get(name)` to check if one exists locally. The project wraps the SDK through `DockerEngineService` but does not call either method in the sandbox deploy path. The fix adds one `pull_image` method to `DockerEngineService` and calls it from the sandbox deploy code. No new library is introduced.

### Key questions
- **Where should the pull happen: inside DockerEngineService.create_container or in the sandbox deploy caller?**: In the sandbox deploy caller, before it calls create_container. (best practice) [sources: src/devops_cli/docker/engine.py]
  - Rejected: Pull inside DockerEngineService.create_container. Rejected. This would add a network check to every container creation, including callers that use locally-built images.
  - Chosen: Pull in the sandbox deploy caller before create_container. Chosen. The sandbox deploy is the path that needs a registry image. The pull is scoped to where it is needed.
  - Rejected: Replace containers.create with containers.run. Rejected. containers.run starts the container immediately, which changes the create-then-start flow the sandbox deploy uses.
- **Should the code check if the image exists locally before pulling?**: Yes. Check with images.get first. Pull only when the image is absent. (best practice) [sources: src/devops_cli/docker/engine.py]
  - Rejected: Always pull. Rejected. A pull makes a network request even when the image is local, adding latency to every deploy.
  - Chosen: Check locally then pull if absent. Chosen. The image is local in the common case. A local check avoids the network round-trip.
- **What is the default sandbox image reference?**: python:3.14-slim [sources: src/devops_cli/docker/sandbox.py]
- **Does the DockerEngineFake in tests already support a pull call?**: The fake holds alpine:3 and scripts container behavior. It does not record a pull call. The test for this fix must add a pull call to the fake and assert it is called when the image is absent. [sources: docs/TESTING.md]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "implement.branch": "fix/2554-devops-sandbox-deploy-fails-with-a", "implement.job": "devops-cli-runner-20261101-113354-b6d0", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.spend": "{\"requests\": 72, \"input_tokens\": 3493323, \"output_tokens\": 22349}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "308d8cfcc65df4fd9de2d7dbb56131af42f2e58e9461fb0748fbdb58d85f30b4", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "abb190942e7dd4b5872787fbdddb7ab9b719d78e707d17bec2b10c3340094890", "stage.branch": "fix/2554-devops-sandbox-deploy-fails-with-a", "stage.file_cap": null, "stage.groups": "[[\"Add pull_image to DockerEngineService\", 3450], [\"Add image pull support to DockerEngineFake\", 3372], [\"Pull image in sandbox deploy before create\", 3381]]", "stage.needs_split": null, "stage.pr": "2996", "stage.ready": "2996", "stage.sha": "6497f83be20e0b6d29490a984b28cca80401c4c3"} -->
