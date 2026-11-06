# Tasks

## 1. A missing tag of a new release is not yet (behavior)

- [x] 1.1 Write the failing tests: `tag_digest` raises `RegistryTagNotFoundError` on 404 and `RegistryReadError` on other statuses; `live_release` skips a new release with a missing `service` or `runner` tag and checks the older ones; it raises for an older release and for HTTP 500; the row posts the `Live since` comment of an older release in the same round; three rounds with a 404 on a new release suspend no row.
  Verification: `uv run devops ci test tests/docker/test_registry_tag_digest.py tests/roadmap/test_roadmap_release_roll.py tests/roadmap/test_roadmap_release_comments.py tests/roadmap/test_roadmap_run.py`
- [x] 1.2 Add `RegistryTagNotFoundError` and export it. Add `CONST_ROADMAP_RELEASE_IMAGE_GRACE_MINUTES`. Raise the new error in `tag_digest`. Give `live_release` the time of the round and the skip rule. Pass `now` from `_live_pass`.
  Verification: `uv run devops ci test tests/docker/test_registry_tag_digest.py tests/roadmap/test_roadmap_release_roll.py tests/roadmap/test_roadmap_release_comments.py tests/roadmap/test_roadmap_run.py tests/argo/test_image_pins.py`

## 2. Documents (documents)

- [x] 2.1 Regenerate `docs/ERRORS.md` and state the rule in `k8s/README.md`.
  Verification: `uv run devops docs generate --check`
- [x] 2.2 Check that the change folder is valid
  Verification: `uv run devops openspec check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
