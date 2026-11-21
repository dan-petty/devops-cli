# Tasks

## 1. The release path rule (behavior)

- [x] 1.1 Write the failing tests: the plan and the round settle a conflict on the version line of a package in `uv.lock`, run `uv lock` once and push only the change of the pull request; a conflict on the version line of `pyproject.toml` still stops; `is_release_path` stops no `version =` line outside `pyproject.toml`.
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py`
- [x] 1.2 Check the version line only in `pyproject.toml` in `is_release_path`, and delete the `__version__` check.
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/roadmap/steps tests/commands/test_roadmap_step_fix_conflict.py`

## 2. Documents

- [x] 2.1 Name the release paths in the spec `roadmap-fix-conflict`, and add the scenario of `uv.lock`.
  - Verification: `$ uv run devops ci --check --only openspec`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
