## Purpose

How `devops argo cd apps status` checks each image that an Argo CD Application pins to a digest against the digest its tag names in its registry, and how it reports a moved tag, an unread registry and a status it cannot read.

## ADDED Requirements

### Requirement: Status checks each pinned image against its registry
`devops argo cd apps status <name>` SHALL read each kustomize image entry `<image>:<tag>@<digest>` of the Application's `spec.source` and `spec.sources`, ask the image's registry for the digest its tag names now with the OCI distribution API, and show one line for each pin: in step, moved with both digests, or not read with the reason.

#### Scenario: The registry moved a pinned tag
- **WHEN** the Application pins `ghcr.io/example/devops-cli/service:latest` to `sha256:aaaa…` and the registry names `sha256:bbbb…` for that tag
- **THEN** the panel shows the image with both short digests, and the command exits 1

#### Scenario: Each pin is in step
- **WHEN** the registry names the pinned digest for the tag
- **THEN** the panel shows the image at its digest, and the command exits 0

#### Scenario: The Application pins no image
- **WHEN** no kustomize image entry names both a tag and a digest
- **THEN** the command sends no request to any registry

### Requirement: The registry read is anonymous and public
The registry read SHALL use the project's egress-checked HTTP client at the public level, answer a 401 Bearer challenge with an anonymous token from the challenge's realm, and raise `RegistryReadError` (`DOCKER_REGISTRY_READ_ERROR`) when the registry gives no anonymous token, no manifest for the tag, or no `Docker-Content-Digest`.

#### Scenario: A registry that refuses anonymous pulls
- **WHEN** the token endpoint of the registry answers 401
- **THEN** the read raises `RegistryReadError` that says the image needs credentials, and the status panel reports the pin as not read and the command exits 1

### Requirement: A status with an error exits 1
Without `--watch`, `devops argo cd apps status` SHALL exit 1 when its panel shows an error: the Argo CD API refused the read, a tag names another digest, or a registry gave no digest. With `--dry-run` it SHALL send no request.

#### Scenario: Argo CD refuses the read
- **WHEN** the Argo CD API answers 401 to the application read
- **THEN** the panel shows the error and the command exits 1

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it prints the action `show_argocd_app_status` and sends no request
