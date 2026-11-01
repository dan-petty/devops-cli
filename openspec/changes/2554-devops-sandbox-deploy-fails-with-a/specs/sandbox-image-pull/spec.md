## Purpose
How `devops sandbox deploy` gets the sandbox image onto the Docker engine before it creates the container: it pulls a missing image, it makes no pull for a local image, and a failed pull names the image and the reason.

## ADDED Requirements

### Requirement: A sandbox deploy pulls a missing image
`WorkloadSandboxEngine.deploy` SHALL ask the engine for the image of the sandbox, and SHALL pull the image when the engine does not hold it, before it creates the container.

#### Scenario: Deploy with a missing image
- **WHEN** the engine holds no image for the reference of the sandbox, such as the default `python:3.14-slim`, and a registry holds it
- **THEN** the engine receives the image lookup, then the pull, then the container creation, and the sandbox is running with no 404 error

### Requirement: A sandbox deploy does not pull a local image
When the engine holds the image of the sandbox, `WorkloadSandboxEngine.deploy` SHALL create the container with no pull request.

#### Scenario: Deploy with an image on the engine
- **WHEN** the engine already holds the image of the sandbox
- **THEN** the engine receives the image lookup and the container creation, and no pull

### Requirement: A refused pull names the image and the reason
When the image lookup or the pull fails, `DockerEngineService.pull_image` SHALL raise `DockerEngineError` with the image reference and the reason of the failure in its text. `devops sandbox deploy` SHALL stop with that text, create no container and leave no sandbox in the registry.

#### Scenario: No registry holds the image
- **WHEN** the sandbox image is not on the engine and no registry holds it
- **THEN** the deploy stops with `SandboxError` whose text holds `Image pull failed for`, the image reference and `pull access denied`, the engine receives no container creation, and the sandbox registry holds no instance

#### Scenario: The image lookup fails
- **WHEN** the engine fails the image lookup with an error other than a missing image
- **THEN** `pull_image` raises `DockerEngineError` with the text `Image lookup failed for` and the image reference, and the engine receives no pull
