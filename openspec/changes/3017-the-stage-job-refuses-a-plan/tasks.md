# Tasks

## 1. Name the creating group in the path problem

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`, `k8s/README.md`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`, `k8s/README.md`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_paths.py`, add a test for a plan in the shape of #2996 (a path that group 3 creates and group 1 reads) that asserts the problem names `group 3 creates it after group 1` and `Move group 3 before group 1` and holds neither `No file has this name` nor the old tail, add a test for a folder that a later group creates a file in, and add a test that a path no group creates keeps the old message, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [x] 1.2 In `src/devops_cli/lang/en/messages.py`, add `stage_problem_path_later`; in `src/devops_cli/roadmap/stage_paths.py`, add `_first_creators` and let `_problem` use the new message when a later group creates the path, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes
- [x] 1.3 In item 15 of `k8s/README.md`, add the sentence that a problem names the later group that creates the path, and run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
