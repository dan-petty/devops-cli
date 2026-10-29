# Design

## Decisions

- **Where the check runs:** in `devops argo cd apps status`, as the issue and its refinement propose. The command already reads the Application through the Argo CD API, and that reply is the Application object, with `spec.source.kustomize.images`. A second command would read the same object again.
- **What is compared:** the pin in `spec.source.kustomize.images` (and in each `spec.sources` entry) against the digest its tag names now. Image Updater writes the pin, and every workload of the Application runs it (checked live: the Deployment, the CronJob and the running pod's `imageID` hold the same digest).
- **What a pin is:** a kustomize image entry `[<name>=]<image>:<tag>@<digest>`. An entry with only a tag or only a digest pins no moving tag, so it is not checked.
- **Registry read:** a `HEAD` of `/v2/<repository>/manifests/<tag>` with the four manifest media types in `Accept`, and an anonymous Bearer token when the registry answers 401 with a challenge. This is the read `crane digest` makes. The client is `new_http_client(level=EgressLevel.PUBLIC)`, so a registry on a private or loopback address is refused and reported as not read.
- **Exit status:** without `--watch`, 1 when the panel shows any error (status not read, tag moved, digest not read), else 0. `--watch` keeps redrawing and exits as before.
- **Errors:** `RegistryReadError` (`DOCKER_REGISTRY_READ_ERROR`) carries why a registry gave no digest. `check_pins` turns it, an egress refusal or an HTTP error into a check with an error, so the other pins are still read.

## Rejected alternatives

- **Read the Application through the Kubernetes API** (`ArgoCRDService`), which needs no Argo CD token (#2576). Rejected for this item: `apps status` reads the Argo CD API today, and moving its transport changes every status read. #2576 owns the token fault.
- **`crane digest` or `skopeo inspect` as a pinned tool.** Neither is in `tools.lock` or on the host. A pin needs a SHA-256 for each platform, and the OCI read is two requests through the client the project already checks.
- **docker-py's `parse_repository_tag` and `resolve_repository_name`.** The import adds a `type: ignore` over the ceiling of 51. `types-docker` would remove the need, but it reports 3 errors in `docker/engine.py`, among them 5 Protocol conflicts with the #2534 seam. #2603 owns that work.
- **Compare with the pod's `imageID`.** A pod runs only while a workload is up; `roadmap-service` can be at 0 replicas and the CronJob is suspended, which is how the 2026-10 fault went unseen (`imagesManaged: 0`). The pin is always there.
- **Docker Hub shorthand (`nginx:1.27`).** Not accepted: the split requires a named registry host, as Image Updater writes references. Such an entry is reported as not read, never as in step.
