# Tasks

## 1. Gate cluster image checks by repository

Kind: behavior. Reads: `src/devops_cli/roadmap/release_roll.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job_rows.py`. Changes: `src/devops_cli/roadmap/release_roll.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job_rows.py`.
Adds: `publishes_release_images`

- [x] 1.1 Add `test_publishes_release_images_matches_only_image_repository` in `tests/roadmap/test_roadmap_release_roll.py` and `test_an_unrelated_repository_posts_released_comments_without_checking_images` in `tests/roadmap/test_roadmap_run_job_rows.py`, and pass the image repository in the two existing adapter roll tests in `tests/roadmap/test_roadmap_run_job_rows.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_release_roll.py tests/roadmap/test_roadmap_run_job_rows.py`
- [x] 1.2 Add `publishes_release_images` to `src/devops_cli/roadmap/release_roll.py` and gate `roll` and `client` in `_run_release_comments_adapter` of `src/devops_cli/roadmap/run.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_release_roll.py tests/roadmap/test_roadmap_run_job_rows.py`

## 2. Update cluster runbook

Kind: other. Reads: `docs/CLUSTER.md`. Changes: `docs/CLUSTER.md`.

- [x] 2.1 Clarify step 20 in `docs/CLUSTER.md` so the documentation states that cluster and registry digest checks run only for the repository that publishes the Service and runner images.
  - Verification: `$ uv run devops ci docs`
