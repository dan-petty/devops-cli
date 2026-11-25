### Problem

No tool reads all the pins of the project. `devops survey` reads pyproject.toml only. `devops k8s image-pins` checks that an image exists, not what it is. Nothing reads GitHub Actions versions, Dockerfile FROM lines, tools.lock sources or chart versions into one list. A research agent cannot watch what it cannot list.

### Expected

`devops research inventory` prints a typed list of components with kind, name, version, ecosystem, purl or registry reference, upstream repository and the file where it is pinned. It reads uv.lock, pyproject.toml, tools.lock (and the Python and Node lock files of tools), Dockerfile and devcontainer files, workflow `uses:` lines, Argo CD Application chart versions, rendered image lines (reuse the renderer of the image-pin check), and tf provider constraints. A file `.devops/research-watch.toml` holds the mapping from a component to its OSV ecosystem and name and extra pins that live outside the repository.

### Acceptance criteria

- Tests that fail on the base: a fixture repository with one pin of each kind gives the expected Component list. The same action at two versions (setup-uv, setup-buildx) shows as two components.
- A test: a pin with no ecosystem mapping appears with ecosystem unknown and is counted, not dropped.
- A test: the reader makes no network request.
- The command is in the CLI reference (`devops docs generate --sync-readme`) and the settings table if it adds a setting.
- No private host name, private address or device path is in the fixtures or the mapping file.

### Existing tool considered

tomllib and PyYAML (already used), the kustomize and helm renderer of `devops k8s image-pins`, `uv.lock` parsing in `devops_cli.ai.kb`. Renovate extracts the same pins but gives no list to code. No new parser library is needed.

### Related

Part of the research agent plan (ADR in item 1). Related: #2044 (survey), #3877.

Part of the research agent plan of 2026-11-07 (design by the research-agent design workflow; the ADR is delivered through #3877).


### Delivered by this pull request

This pull request delivers the first slice: `devops research inventory`, with a typed Component list (kind, ecosystem, name, version, file, line), JSON and YAML output, a count of each kind and ecosystem, and the count of components with the ecosystem `unknown`. It reads uv.lock, pyproject.toml, tools.lock with its requirement and Node lock files, Dockerfiles, the devcontainer lock, workflow `uses:` lines, Argo CD Application chart versions, the images named in the YAML under k8s/, and Terraform provider constraints. It makes no network request and starts no program.

Moved to #3932: the file `.devops/research-watch.toml` (OSV ecosystem and name, pins outside the repository), the purl and upstream repository of a component, and the images that Helm renders (the render needs the network).


<!-- devops-roadmap-record {"Effort": "High", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
