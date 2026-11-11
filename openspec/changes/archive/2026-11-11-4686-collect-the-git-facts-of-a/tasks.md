# Tasks

## 1. Behavior: the window resolver

- [x] 1.1 Add the failing tests and the recorded git scenario `review_window`: a fixture repository with tags in three time zones, the base tag out of a version window, a week from Monday to Monday in UTC, two times in UTC, the last days, a safe window id, the previous window, and the refusals
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_window.py`
- [x] 1.2 Add `parse_window`, `read_tags` and `resolve_window` in `src/devops_cli/roadmap/project_review/window.py`, the git command builders in `git_read.py`, and `RoadmapReviewError`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_window.py`

## 2. Behavior: the git facts and data.json

- [x] 2.1 Add the failing tests: the facts of a version window, a hot file that counts the commits at its old name, numstat with renames, binary files and paths with spaces, a complexity fact that is skipped with no lizard, a fact that is not ok with no reason, and data.json with its JSON Schema
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py`
- [x] 2.2 Add the facts in `src/devops_cli/roadmap/project_review/facts.py` and the model of data.json in `data.py`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_facts.py`

## 3. Behavior: the command

- [x] 3.1 Add the failing tests: a dry run starts no program and lists the git commands, two windows are refused before any read, a run writes data.json under the data directory and prints it, and a repository that is not the origin is refused
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py`
- [x] 3.2 Add `devops roadmap review run` in `src/devops_cli/commands/roadmap_review.py` and `src/devops_cli/roadmap/project_review/review.py`, with its help and messages
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_review.py`

## 4. Other: the extra review and the generated files

- [x] 4.1 Add lizard 1.24.3 in the optional extra `review` of `pyproject.toml`, in `uv.lock`, in the devcontainer image and in the Service image, and mark the generated files `linguist-generated` in `.gitattributes`
  - Verification: `$ uv lock --check`

## 5. Documents

- [x] 5.1 Regenerate the command reference, the error catalog and the command matrix of the README
  - Verification: `$ uv run devops docs generate --sync-readme --check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
