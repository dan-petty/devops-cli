# Tasks

## 1. The latest rule and the chart render

- [x] 1.1 Write the failing tests in `tests/k8s/test_image_pins.py`: the `names_latest` predicate, the `latest` images of a path Application and of a chart value file, `--skip-tests` in the chart command, and the command's refusal before it resolves (`uv run devops ci test tests/k8s/test_image_pins.py`).
- [x] 1.2 Add `names_latest` and `ImagePins.latest` to `src/devops_cli/k8s/image_pins.py`, add `--skip-tests` to the chart command, and make `devops k8s image-pins` refuse the `latest` images before it resolves (`uv run devops ci test tests/k8s/test_image_pins.py`).
- [x] 1.3 Update `k8s/README.md` (Image Pins) and `docs/SDLC.md` (the job), and run `uv run devops docs generate --sync-readme`.
- [x] 1.4 Check the render of the repository with `collect_image_pins` (no resolve): no image names `latest`, and no test pod's image is in the pins.

## Workflow follow-up

- #2610 resolves each pin with a HEAD request that Docker Hub does not count.
- #2603 moves the reference split of `src/devops_cli/k8s/image_pins.py` to the Docker SDK's parser.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
