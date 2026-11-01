# Tasks

## 1. Warn on a long body in the readiness verdict

Reads: `src/devops_cli/github/merge_readiness.py`, `tests/github/test_merge_readiness.py` (the helpers `_pr`, `_assess`, `_warning` and the test `test_a_clean_grounded_pull_request_is_ready`), `tests/commands/test_pr.py` (the helper `_pr` and the table `test_check_readiness_prints_the_verdict_and_exits_on_it`), `src/devops_cli/lang/en/messages.py` (the class `PRMessages`, lines 1047 to 1344). Changes: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`.

- [ ] 1.1 Write the failing tests first. In `tests/github/test_merge_readiness.py` add a table over `_assess(tmp_path, _pr(body=...))` with these rows: 1,000 characters give no advisory; 1,001 characters give exactly one WARNING whose text holds `1,001`, `1,000` and `CONTRIBUTING.md`; 1,000 characters followed by a blank line and the five trailer lines (`Closes #704`, `Change: ...`, `Fail-to-pass: ...`, `Co-authored-by: ...`, `Signed-off-by: ...`) give no advisory; a body of `None` and a body with `\r\n` line ends give no advisory; the long body leaves `blockers` empty and `is_ready` true. In `tests/commands/test_pr.py` add a row to the table `test_check_readiness_prints_the_verdict_and_exits_on_it`: `g.pull(_pr(body="x" * 1001))` gives exit 0 and the output holds `1,001`
  - Verification: `uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py` fails on the base: the 1,001-character rows find no advisory. The 1,000-character rows pass on the base and pin the limit.
- [ ] 1.2 In `src/devops_cli/lang/en/messages.py` add `pr_body_too_long` to `PRMessages`. In `src/devops_cli/github/merge_readiness.py` add `_PR_BODY_MAX_CHARS`, `_TRAILER_PREFIXES` and `_judge_body_length(verdict, pr_data, pr_num)`. Call it in `assess_merge_readiness` after `_judge_draft`
  - Verification: `uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py` passes
- [ ] 1.3 Check the callers that share the verdict
  - Verification: `uv run devops ci test tests/github tests/commands/test_pr.py tests/commands/test_pr_cmd.py` passes

## 2. Name the advisory in CONTRIBUTING.md

Reads: `CONTRIBUTING.md` (section 4, the bullet "The Body Is the Commit Message"). Changes: `CONTRIBUTING.md`.

- [ ] 2.1 In `CONTRIBUTING.md` section 4, replace the sentence "A reviewer checks the length of the body." with "`devops pr check-readiness` warns when the body is longer than 1,000 characters before the trailers, and the warning blocks nothing."
  - Verification: `git grep -n "A reviewer checks the length of the body" -- CONTRIBUTING.md` prints nothing, and `git grep -n "check-readiness. warns when the body" -- CONTRIBUTING.md` prints the line
- [ ] 2.2 Check the documents
  - Verification: `uv run devops ci docs` and `uv run devops openspec check` pass
