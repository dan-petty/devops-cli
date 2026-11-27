# Tasks

## 1. Read the version of a Plan

Kind: behavior.

Reads: `src/devops_cli/k8s/image_pins.py`, `tests/k8s/test_image_pins.py`.

Changes: `src/devops_cli/k8s/image_pins.py`, `tests/k8s/test_image_pins.py`.

- [x] 1.1 Write the tests of a Plan with a version, a Plan with a channel and no version, and a Plan image with its own tag or digest, and watch the test of the version fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py`
- [x] 1.2 Give the untagged `prepare` and `upgrade` image of a Plan the version of the Plan in `image_nodes`.
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Name the tag that an untagged image of a Mattermost object and of a Plan takes in `docs/CLUSTER.md` (Image Pins).
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
