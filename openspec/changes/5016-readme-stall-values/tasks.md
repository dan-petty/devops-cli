# Tasks

## 1. The Kubernetes README states the real deadline values

Kind: documents. Changes: `k8s/README.md`, `tests/roadmap/implement/test_roadmap_implement_deadline_settings.py`.

- [x] 1.1 Add the test case that reads `k8s/README.md` and compares the stall, the extension, the ceiling, the watch, the margin and the stall time in minutes with the defaults. On the base it fails for the watch, the stall and the minutes.
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_deadline_settings.py`
- [x] 1.2 Change the Deadline bullet of Runner Jobs to a stall of 4200 s and a watch of 3600 s, and item 16 of the Service rows to a stall of 70 minutes.
  - Verification: `$ ! git grep -n -F -e "default 2400" -- k8s/README.md`
