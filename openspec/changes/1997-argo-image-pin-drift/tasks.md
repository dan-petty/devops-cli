# Tasks

## 1. The status command checks each pinned image

- [x] Add failing tests: the pins of an Application, the reference split, the anonymous registry read and its errors, and the status command's lines, exit status and dry run, with the Argo CD API and the registry faked at the HTTP edge
  - Verification: `uv run devops ci test tests/argo/test_image_pins.py tests/docker/test_registry_tag_digest.py tests/commands/test_argo_apps_status.py`
- [x] Add `RegistryReadError`, `docker/registry.py` (the OCI digest read) and `argo/image_pins.py` (the pins and their checks), and wire them into `devops argo cd apps status` with `--dry-run` and exit 1 on an error
  - Verification: `uv run devops ci test tests/test_argo.py tests/argo tests/docker tests/commands/test_argo_apps_status.py`
- [x] Name the command in `k8s/README.md` step 4 and Service Image Updates, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1997-argo-image-pin-drift`

## Workflow follow-up

- #2603 types docker-py with `types-docker` and moves the reference split to docker-py's parser.
- #2576 makes a refused Argo CD token a one-line error and mints a new token.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
