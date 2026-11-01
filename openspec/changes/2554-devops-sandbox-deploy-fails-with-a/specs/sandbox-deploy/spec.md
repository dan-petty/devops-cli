## Purpose
The behavior of devops sandbox deploy when it creates a container from a registry image on the local Docker engine.

## ADDED Requirements

### Requirement: pull-missing-image-before-container-creation
When the sandbox image is not present on the local engine, the deploy command SHALL pull the image before it creates the container.

#### Scenario: deploy with a missing image
- **WHEN** The engine has no image matching the sandbox image reference
- **THEN** The command pulls the image and then creates the container without a 404 error

### Requirement: skip-pull-when-image-exists-locally
When the sandbox image is already present on the local engine, the deploy command SHALL NOT issue a registry pull request.

#### Scenario: deploy with an existing image
- **WHEN** The engine already has an image matching the sandbox image reference
- **THEN** The command creates the container without a network pull call

### Requirement: name-image-in-pull-failure-error
When the image pull fails, the error message SHALL contain the image reference and the reason for the failure.

#### Scenario: pull fails due to a registry error
- **WHEN** The image pull fails because the registry is unreachable or the image does not exist in the registry
- **THEN** The error message contains the image reference and the failure reason
