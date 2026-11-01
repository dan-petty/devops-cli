# Tasks

## 1. Add body-length advisory to merge_readiness

Reads: none. Changes: `src/devops_cli/github/merge_readiness.py`, `tests/test_merge_readiness.py`.

- [ ] 1.1 Write a table test in `tests/test_merge_readiness.py` with four rows: (1) body of exactly 1,000 chars with no trailers gives no advisory; (2) body of 1,001 chars gives one WARNING advisory whose text contains "1,001", "1,000" and "CONTRIBUTING.md"; (3) body of 1,000 chars plus trailer lines gives no advisory; (4) the exit code of `devops pr check-readiness` is the same with and without the advisory. Each row calls `assess_merge_readiness` with a `pr_data` dict whose "body" key holds the test text, and asserts on `verdict.advisories` and `verdict.is_ready`, and verify that `uv run devops ci test tests/test_merge_readiness.py` fails on the base
- [ ] 1.2 In `src/devops_cli/github/merge_readiness.py`: (1) add `PR_BODY_MAX_LENGTH = 1000` as a module-level constant beside `assess_merge_readiness`. (2) add `_TRAILER_PREFIXES = ("Closes", "Change:", "Fail-to-pass:", "Co-authored-by:", "Signed-off-by:")` as a module-level tuple. (3) add `_strip_trailers(body: str) -> str` that removes lines starting with any prefix in `_TRAILER_PREFIXES` and returns the remaining text. (4) add `_judge_body_length(verdict: _Verdict, pr_data: dict[str, Any], pr_num: int) -> None` that reads `pr_data.get("body", "")`, strips trailers, and calls `verdict.warn(...)` with a message naming the length, the limit, and CONTRIBUTING.md section 4 when the length exceeds `PR_BODY_MAX_LENGTH`. (5) call `_judge_body_length(verdict, pr_data, pr_num)` in `assess_merge_readiness` after `_judge_draft` and before `_judge_checks`, and verify that `uv run devops ci test tests/test_merge_readiness.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Update CONTRIBUTING.md section 4

Reads: none. Changes: `CONTRIBUTING.md`.

- [ ] 2.1 No test for a documentation change, and verify that `uv run devops docs check` fails on the base
- [ ] 2.2 In CONTRIBUTING.md section 4, under the bullet "The Body Is the Commit Message", replace the sentence "A reviewer checks the length of the body." with "`devops pr check-readiness` warns when the body is longer than 1,000 characters before the trailers.", and verify that `uv run devops docs check` passes
- [ ] 2.3 CONTRIBUTING.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
