# Tasks

## 1. The template of the stage repository

Kind: test-only edit. Changes: `tests/support/roadmap_stage.py`.

- [x] 1.1 Move the build of the repository from `stage_repo` into `_build_stage_repo`, and add the session fixture `stage_repo_template`, which builds it once in each test process under `tmp_path_factory`.
  - Verification: `$ uv run devops ci test tests/roadmap`
- [x] 1.2 Make `stage_repo` copy the template into `tmp_path` with `shutil.copytree`, set the URL of the clone's `origin` to the copy, and refresh the index of the clone.
  - Verification: `$ uv run devops ci test tests/roadmap`

## 2. Documents

Kind: documents. Changes: `docs/TESTING.md`.

- [x] 2.1 Replace the closed issues #2174 and #2178 to #2183 in the "Not yet" list with the move of the tests that start real git to `git_fake` (#7533), and say in "Run time" that `stage_repo` copies a template that each test process builds once.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The move of the tests that start real git through `stage_repo`, its layers and `git_for_real` to `git_fake` transcripts: #7533.
