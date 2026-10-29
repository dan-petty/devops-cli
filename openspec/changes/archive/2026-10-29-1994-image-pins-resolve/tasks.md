# Tasks

## 1. The image pins resolve before the merge

- [x] Add failing tests: the image values of rendered objects, the registry split held to the Docker SDK, the local registry rule, the sort of a path and a chart Application with a tab after a value, a chart that does not render, an OCI chart repository, the resolution of each recorded run, the anonymous configuration, a manifest with no digest, the command's pass, fail and dry run
  - Verification: `uv run devops ci test tests/k8s/test_image_pins.py`
- [x] Add the shared fake of `docker buildx imagetools inspect`, its recording script and record, and its contract suite
  - Verification: `uv run devops ci test tests/k8s/test_imagetools_contract.py`
- [x] Add `src/devops_cli/k8s/image_pins.py`, the command `devops k8s image-pins` and `ImagePinError`
  - Verification: `uv run devops ci test tests/k8s/test_image_pins.py tests/k8s/test_imagetools_contract.py`
- [x] Add the failing workflow contract, then the `image-pins` job of `ci.yml` and its two allowlisted run steps
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py tests/test_ci.py`
- [x] Describe the job in `docs/SDLC.md`, the command in `k8s/README.md` and the fake in `docs/TESTING.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1994-image-pins-resolve`

## Workflow follow-up

- #2610: the resolver moves to a HEAD request (`crane digest`), which Docker Hub does not count.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
