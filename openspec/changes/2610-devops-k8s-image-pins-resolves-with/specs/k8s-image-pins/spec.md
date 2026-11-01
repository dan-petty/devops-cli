## MODIFIED Requirements

### Requirement: Each pin resolves in its registry as an anonymous client
The command SHALL resolve each pinned image once with a HEAD request of its manifest to the registry, through the HTTP client of the project at the public egress level, as an anonymous client. It SHALL answer a 401 Bearer challenge with an anonymous token from the realm of the challenge, and SHALL send no stored credential. A Docker Hub name SHALL go to the host `registry-1.docker.io`, and a repository of one component SHALL go under `library/`. An image with a digest SHALL resolve by that digest. The command SHALL exit 1 when an image does not resolve, naming the image, its Applications, its registry and the error of the resolver.

#### Scenario: A tag that its registry does not hold
- **WHEN** the registry answers the HEAD of a pinned image with 404
- **THEN** the command exits 1 and names the image, its Application, its registry and the error line `The registry gives no manifest for <image> (HTTP 404).`

#### Scenario: Each pin resolves
- **WHEN** each pinned image resolves to a digest
- **THEN** the command exits 0 and reports the number of resolved images

#### Scenario: A Docker Hub name
- **WHEN** the pins are `nginx:1.27`, `valkey/valkey:9.1.2-alpine` and `docker.io/traefik:v3.7.16`
- **THEN** the HEAD requests go to the host `registry-1.docker.io` for the repositories `library/nginx`, `valkey/valkey` and `library/traefik`, no request goes to the host `docker.io`, and the registry column shows `docker.io`

#### Scenario: A registry that asks for a token
- **WHEN** the registry answers the first HEAD with 401 and a Bearer challenge
- **THEN** the client sends one token request to the realm of the challenge with no credential, sends the HEAD again with the token, and the image resolves

#### Scenario: A reference with a digest
- **WHEN** a pinned image is `ghcr.io/example/app:1.0@sha256:<digest>`
- **THEN** the HEAD goes to the manifest of that digest, and the image resolves to it

#### Scenario: A registry that refuses an anonymous client
- **WHEN** the token endpoint of the registry answers 401
- **THEN** the command exits 1 and the error line says that reading the image needs credentials

#### Scenario: A manifest read sends no GET
- **WHEN** the command resolves its pins
- **THEN** each request to a manifest is a HEAD

### Requirement: A dry run renders and resolves nothing
`devops k8s image-pins --dry-run` SHALL start no render and no resolve, SHALL send no request, and SHALL name the request that a run sends for each image.

#### Scenario: A dry run
- **WHEN** a person runs `devops k8s image-pins --dry-run`
- **THEN** no request reaches a registry and the output names `HEAD https://<registry>/v2/<repository>/manifests/<reference>`

### Requirement: The CI job checks a pull request that changes the pins
The `image-pins` job of `ci.yml` SHALL run `devops k8s image-pins` on a pull request that changes `k8s/`, the command's modules, the registry module `src/devops_cli/docker/registry.py` or `ci.yml`, with read-only permissions and the pinned helm, and SHALL skip the check on any other pull request.

#### Scenario: The job's steps
- **WHEN** `ci.yml` is read
- **THEN** the job `image-pins` has a paths filter on `k8s/**`, `src/devops_cli/**/image_pins.py`, `src/devops_cli/docker/registry.py` and `.github/workflows/ci.yml`, the permissions `contents: read` and `pull-requests: read`, and runs `uv run devops k8s image-pins` only when the filter matches
