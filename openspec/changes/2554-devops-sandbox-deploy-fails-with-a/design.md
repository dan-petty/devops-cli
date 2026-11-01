# Design

## Decisions

- **The pull sits in `WorkloadSandboxEngine._spawn_container`, before `create_container`.** `devops sandbox deploy` runs this code. The check and the pull cost nothing for a dry run, because `deploy(dry_run=True)` returns before `_spawn_container`. A pull error leaves `deploy` through its existing rollback: the registry record is removed and the error becomes `SandboxError`, whose text starts `Failed deploying sandbox container:`.
- **`DockerEngineService.pull_image(image)` is the one seam.** It is a method of the service because every Docker call of devops-cli goes through the service, and the fake and the contract suite sit behind it.
- **The presence check uses `images.get`.** `images.get("python")` asks for `python:latest`, as `create` does, so the check and the create agree on the image. `ImageNotFound` means pull. Any other error raises `DockerEngineError` with the text `Image lookup failed for <image>: <reason>` and starts no pull.
- **The pull uses `images.pull(image)`.** The SDK reads the tag from the reference and drains the pull stream. A refused pull raises `DockerEngineError` with the text `Image pull failed for <image>: <reason>`, with `image=<image>` in its details, and the original error as cause.
- **The fake answers as the engine does.** `images.get` of an image the fake does not hold raises `ImageNotFound` with `No such image: <ref>`. `images.pull` of a reference that the fake holds returns it. `images.pull` of a reference that a test published with `publish_image` adds a local image. Any other reference raises `ImageNotFound` with `pull access denied for <repository>, repository does not exist or may require 'docker login'`. The two error texts are those of the engine, recorded on 2026-11-01. A test makes a pull fail in other ways with the existing `fail("images.pull", error)`.
- **A new contract scenario `image_pull` is recorded from a real engine.** It reads a local image, reads a missing image, pulls a missing image that no registry holds, and pulls `alpine:3`. The fake and the replayed SDK must show the same.
- **The dry-run plan lists the image requests.** `plan_sandbox_deploy` adds `GET /images/<image>/json` and `POST /images/create?fromImage=<image>`, the second marked as sent only when the image is not on the engine. Both come before the container creation, in the order the real run sends them.

## Rejected alternatives

- **Pull inside `DockerEngineService.create_container`.** `create_container` serves other callers, such as the workload runner, which may use a local image. A pull there adds a registry call to every creation. Evidence: `git grep -n "create_container" -- src` lists two callers with different needs.
- **Replace `containers.create` with `containers.run`.** `containers.run` starts the container at once. `_spawn_container` creates it, starts it and returns its ID, and `deploy` records the instance between creation and start. The registry record and the rollback need that order.
- **Always pull.** A pull is a registry request even for a local image. It slows each deploy and fails offline when the image is local. The issue also asks for no pull call when the image is local.
- **Check with `images.list(name=image)`, which `list_images` already wraps.** The `reference` filter of `list` matches a repository name without a tag against any tag. So `python` would count as local when only `python:3.12` is local, and the create of `python:latest` would fail with the 404 again. `images.get` has no such gap.
- **Refuse the pull and print the image and the `docker pull` command.** The issue allows this only "if the design refuses pulls". The refined design of the issue chose the pull, and the SDK has the call.
- **Record only the missing-image case in the contract scenario.** The fake would then have a success path that no recording backs. The scenario pulls `alpine:3` as well.
