# Tasks

## 1. Behavior: the dependencies of each image lie in their own layers

- [x] 1.1 Add the failing tests: the `lock` stage exports the requirements without the project, no stage under `runner` or `service` builds on `builder` or copies from the build context, `deps` and `runner-deps` install the lock requirements with `--require-hashes`, a final stage copies only the project from `builder` after its apt upgrade, and each uv install mounts the uv cache. Point the runner, Service, hook, tool-table and Debian release tests at the stages that now hold their instructions
  - Verification: `$ uv run devops ci test tests/invariants/test_image_layers.py tests/invariants/test_runner_image.py tests/invariants/test_runner_hooks.py tests/invariants/test_service_image.py tests/roadmap/test_roadmap_runner_tools.py tests/invariants/test_architectural_invariants.py`
- [x] 1.2 Split the `Dockerfile` into the `lock`, `deps`, `builder`, `runner-tools`, `runner-deps`, `runner`, `service-deps` and `service` stages, mount the uv cache in each uv install, and delete the second `uv sync`, the `rm -rf` of the uv cache and npm, and the copy of the whole venv
  - Verification: `$ uv run devops ci test tests/invariants/test_image_layers.py tests/invariants/test_runner_image.py tests/invariants/test_runner_hooks.py tests/invariants/test_service_image.py tests/roadmap/test_roadmap_runner_tools.py tests/invariants/test_architectural_invariants.py tests/invariants/test_mcp_server_image.py`

## 2. Documents

- [x] 2.1 Describe the stages, the layers and their measured sizes in the Image paragraph of `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4814 gives the runner pod an offline venv from a uv cache in the image: the first `uv` child of an implement Job under 30 s, and `uv sync --locked --offline` of a checkout in at most 60 s.
- Pending a person: after a release with this change rolls out, check that a runner Job on a node that holds the previous release starts its container in 10 s or less, and after 7 days that the median from Job create to container start is 10 s or less.
