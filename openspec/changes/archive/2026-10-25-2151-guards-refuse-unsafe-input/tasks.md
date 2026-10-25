# Tasks

## 1. The subprocess environment guard refuses unsafe overrides

- [x] 1.1 Add parametrized tests to `tests/test_subprocess_env_boundary.py`: each of the six refused keys, in upper and in lower case, and a null byte in a key and in a value, with isolation on and off, raise `SecurityError` with the message that names the key (`uv run devops ci test tests/test_subprocess_env_boundary.py`).
- [x] 1.2 In a scratch copy of the base, remove the refused-key check, make it case-sensitive, and remove each part of the null-byte check in turn, and see the new tests fail each time (`.venv/bin/python -m pytest -k "caller_override_that_loads or null_byte" tests/test_subprocess_env_boundary.py`).

## 2. The review target guard keeps a review inside the repository

- [x] 2.1 Add `tests/review/test_review_targets_stay_inside_the_repository.py`: a target outside the root raises `SecurityError`, a symlinked target file gives `[]`, and a directory target leaves out its symlinks and each file that a pattern reaches through a symlinked directory (`uv run devops ci test tests/review/test_review_targets_stay_inside_the_repository.py`).
- [x] 2.2 In a scratch copy of the base, remove the outside-root error, the symlink check of a target file, the symlink check of a candidate and the real-path check of a candidate in turn, and see a new test fail each time (`.venv/bin/python -m pytest tests/review/test_review_targets_stay_inside_the_repository.py`).
- [x] 2.3 Delete the unreachable second condition of the symlink check of a target file, and the unreachable `except OSError, RuntimeError` of the candidate filter, in `src/devops_cli/review/targets.py` (`uv run devops ci test tests/review/test_review_targets_stay_inside_the_repository.py tests/test_review_sample_validation.py tests/test_review_path.py`).
- [x] 2.4 Run the tests on the stock path of a GitHub runner (`env PATH=/usr/bin:/bin .venv/bin/python -m pytest tests/test_subprocess_env_boundary.py tests/review/test_review_targets_stay_inside_the_repository.py`).

## 3. Verification

- [x] 3.1 Run the static checks and the OpenSpec gate (`uv run devops ci --only lint,format,typecheck,docs,openspec,security`, `uv run devops openspec check`).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
