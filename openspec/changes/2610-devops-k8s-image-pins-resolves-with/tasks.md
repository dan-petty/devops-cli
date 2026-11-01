# Tasks

## 1. Resolve image pins with tag_digest HEAD

Reads: `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/docker/registry.py`, `tests/k8s/test_image_pins.py`, `tests/docker/test_registry_tag_digest.py`. Changes: `src/devops_cli/k8s/image_pins.py`, `tests/k8s/test_image_pins.py`.

- [ ] 1.1 Write a test in tests/k8s/test_image_pins.py that calls resolve_image with an httpx2 client whose MockTransport answers HEAD with a 200 and Docker-Content-Digest header, and asserts the returned PinResolution holds that digest and no subprocess was started, and verify that `uv run pytest tests/k8s/test_image_pins.py -x` fails on the base
- [ ] 1.2 In src/devops_cli/k8s/image_pins.py, remove the inspect_command function. Add a _normalize_reference helper that prepends docker.io/library/ when the first path component names no registry host (no dot, no colon, not localhost). Change resolve_image to accept an httpx2.Client parameter and call tag_digest from devops_cli.docker.registry with the normalized reference. Catch RegistryReadError and return a PinResolution with the error text. Change resolve_image_pins to accept and pass the client. In tests/k8s/test_image_pins.py, remove the ImagetoolsFake import and fixture usage. Write a test that builds an httpx2 client with a MockTransport answering HEAD with a 200 and Docker-Content-Digest header, calls resolve_image, and asserts the PinResolution holds that digest. Write a test for the 401-then-200 Bearer token flow. Write a test for a 404 that asserts the error is recorded, and verify that `uv run pytest tests/k8s/test_image_pins.py -x` passes

## 2. Replace image_reference with tagged_image

Reads: `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/docker/registry.py`. Changes: `src/devops_cli/k8s/image_pins.py`.

- [ ] 2.1 Write a test in tests/k8s/test_image_pins.py that calls collect_image_pins with a fixture Application naming a Docker Hub shorthand image (nginx:1.27) and a full-registry image (ghcr.io/org/app:1.0), and asserts both are classified as pinned with the correct registry and repository, and verify that `uv run pytest tests/k8s/test_image_pins.py -x` fails on the base
- [ ] 2.2 In src/devops_cli/k8s/image_pins.py, remove the image_reference function. In collect_image_pins, replace the image_reference call with _normalize_reference followed by tagged_image from devops_cli.docker.registry. Use the TaggedImage fields for registry and repository classification. In updater_repositories, replace the image_reference call the same way. Remove the _DEFAULT_REGISTRY and _DEFAULT_REGISTRY_ALIAS constants if they are no longer referenced. Keep names_latest and is_local_registry unchanged, and verify that `uv run pytest tests/k8s/test_image_pins.py -x` passes

## 3. Remove ImagetoolsFake and contract suite

Reads: `tests/support/fakes/imagetools.py`, `tests/k8s/test_imagetools_contract.py`, `tests/support/imagetools_recording.py`. Changes: `tests/support/fakes/imagetools.py`, `tests/k8s/test_imagetools_contract.py`, `tests/support/imagetools_recording.py`, `tests/fixtures/imagetools_runs/recorded_runs.json`.

- [ ] 3.1 Delete tests/support/fakes/imagetools.py, tests/k8s/test_imagetools_contract.py, tests/support/imagetools_recording.py, and tests/fixtures/imagetools_runs/recorded_runs.json. Remove the imagetools fixture registration from tests/support/bootstrap.py. Remove any import of the imagetools fixture from tests/k8s/test_image_pins.py if a reference remains after group 1, and verify that `! git grep -n ImagetoolsFake src/ tests/` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
