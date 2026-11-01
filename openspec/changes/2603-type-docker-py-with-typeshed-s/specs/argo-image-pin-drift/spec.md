## ADDED Requirements

### Requirement: tagged_image splits reference with docker-py parser
tagged_image SHALL split a reference using docker.utils.parse_repository_tag and docker.auth.resolve_repository_name. A reference that names no registry host SHALL resolve to the default registry docker.io.

#### Scenario: reference with explicit registry
- **WHEN** tagged_image is called with ghcr.io/org/img:tag
- **THEN** it returns TaggedImage with registry ghcr.io, repository org/img, and tag tag

#### Scenario: reference without registry host
- **WHEN** tagged_image is called with org/img:tag
- **THEN** it returns TaggedImage with registry docker.io, repository org/img, and tag tag
