# Proposal

## Why

Issue #1997: from 2026-10-10 to 2026-10-23 the `devops` Application stayed on an old digest of `ghcr.io/dan-petty/devops-cli/service:latest`. ImageUpdater `devops` stayed Ready with `imagesManaged: 0`, and no condition, metric or alert said so. `k8s/README.md` (GitOps, step 4) asked a person to compare the Application's `spec.source.kustomize.images` with the registry by hand, and no command did it.

## What Changes

- `devops argo cd apps status <name>` reads the kustomize images of each source of the Application (`spec.source` and each entry of `spec.sources`). Each entry `<image>:<tag>@<digest>` is a pin.
- For each pin, the command asks the image's registry which digest the tag names now, with the OCI distribution API: a `HEAD` of the tag's manifest, which gives `Docker-Content-Digest`. A registry that answers 401 with a Bearer challenge gets an anonymous pull token from the realm of the challenge, as `crane` and `docker pull` do. The client is the project's egress-checked client at the public level.
- The status panel shows one line for each pin: in step, moved (both digests), or not read (the reason). An Application with no pin sends no registry request.
- Without `--watch`, the command exits 1 when the panel shows an error: the status cannot be read, a tag names another digest, or a registry gives no digest. Before this change, a status that could not be read exited 0.
- The command takes `--dry-run`, which sends no request.
- A new error class, `RegistryReadError` (`DOCKER_REGISTRY_READ_ERROR`), says why a registry gave no digest.
- `k8s/README.md` step 4 names the command in place of the manual comparison.
- The command's output and exit status change, so the change carries a spec delta: the new capability `argo-image-pin-drift`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `argo-image-pin-drift`: how `devops argo cd apps status` checks each image an Application pins against the digest its tag names in its registry.

## Impact

- `src/devops_cli/commands/argo.py`, new `src/devops_cli/argo/image_pins.py`, new `src/devops_cli/docker/registry.py`, `src/devops_cli/exceptions/docker.py`, `src/devops_cli/output/formatters/panels.py`, `src/devops_cli/lang/en/messages.py`.
- `k8s/README.md`, and the regenerated `docs/CLI_REFERENCE.md`, `docs/ERRORS.md`, `docs/MCP_TOOLS.md` and `docs/commands/argo.md`.
- New tests: `tests/argo/test_image_pins.py`, `tests/docker/test_registry_tag_digest.py`, `tests/commands/test_argo_apps_status.py`, and the fake `tests/support/fakes/oci_registry.py`.

## Feasibility

Checked read-only on 2026-10-29:

- Application `devops` has `spec.source.kustomize.images` = `["ghcr.io/dan-petty/devops-cli/service:latest@sha256:fdf792c7…"]`, and `status.summary.images` names the same reference. ImageUpdater `devops` has `forceUpdate: true`, `updateStrategy: digest`, and the condition "Reconciled 1 applications, 0 images updated".
- Deployment `roadmap-service` and CronJob `devops-cli` run the same pinned reference, and the running `roadmap-service` pod's `imageID` is the same digest. So the Application's pin is the deployed digest, and the command reports the pin: it is what Image Updater writes and what every workload runs.
- GHCR: `HEAD https://ghcr.io/v2/dan-petty/devops-cli/service/manifests/latest` with no token answers 401 with `Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:dan-petty/devops-cli/service:pull"`. The token endpoint gives an anonymous token, and the `HEAD` with it answers 200, `application/vnd.oci.image.index.v1+json`, `Docker-Content-Digest: sha256:fdf792c7…`, the digest of the pin. The image is public, so no credential is needed.
- A live run of the new command gave the same result (PR comment).

## Existing Tool Considered

- `crane digest` (go-containerregistry), `skopeo inspect` and `regctl` read a tag's digest without a pull. None is in `tools.lock`, none is on the host, and a binary tool needs a pin with a SHA-256 for each platform in `tools.lock`. The OCI distribution API through the project's HTTP client, which the issue names as an option, needs two requests and no new tool, and keeps the egress check.
- docker-py 7.2.0, a dependency, has `parse_repository_tag` and `resolve_repository_name`. Its package has no type hints, so importing it adds a `# type: ignore[import-untyped]`, and the `src type: ignore` ceiling is at its value, 51. typeshed's `types-docker` 7.2.0 would type it: with it installed, mypy reports 9 of the existing ignores as unused, but it also reports 3 new errors in `docker/engine.py`, among them 5 conflicts between `DockerClient` and the `EngineClient` Protocol of #2534. That rework is outside this item, so the change splits a reference with 10 lines of its own, and #2603 adopts `types-docker` and moves the split to docker-py.
- Written cost of the split (rule 3): about 3k tokens to write, 2k tokens of tests (7 table cases), no upkeep while the distribution reference grammar holds, and minutes of elapsed time. It accepts only a reference that names its registry host, as Image Updater writes it.
- The standard library parses the Bearer challenge (`urllib.request.parse_http_list` and `parse_keqv_list`).
- Internal code deleted: none. The manual comparison in `k8s/README.md` step 4 is replaced by the command.
