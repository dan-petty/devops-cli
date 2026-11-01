## ADDED Requirements

### Requirement: HEAD resolution
devops k8s image-pins SHALL resolve each pinned image with a HEAD request of the manifest via tag_digest, not a GET request or a subprocess call.

#### Scenario: Anonymous HEAD to Docker Hub
- **WHEN** An anonymous client resolves a Docker Hub image pin through tag_digest
- **THEN** ratelimit-remaining is unchanged after the resolution

#### Scenario: 401 Bearer token challenge
- **WHEN** The registry answers the first HEAD with 401 and a Bearer challenge
- **THEN** the client obtains an anonymous token and retries the HEAD, and the digest is returned

#### Scenario: Registry returns 404
- **WHEN** The registry answers the HEAD with 404
- **THEN** the PinResolution holds an error and no digest

### Requirement: No subprocess for resolution
devops k8s image-pins SHALL NOT resolve an image pin by calling a subprocess. The resolution SHALL use an httpx2 client.

#### Scenario: No docker or buildx process
- **WHEN** resolve_image is called with a valid httpx2 client
- **THEN** no subprocess is started and the digest is read from the HTTP response headers
