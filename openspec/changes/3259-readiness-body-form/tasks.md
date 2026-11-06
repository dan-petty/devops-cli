# Tasks

## 1. Judge the body form in the readiness verdict

Reads: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/roadmap/pull_form.py` (`body_problems`), `tests/github/test_merge_readiness.py` (the helpers `_pr`, `_assess` and the test `test_the_body_warns_over_the_limit`), `tests/commands/test_pr.py` (the helper `_pr` and the table `test_check_readiness_prints_the_verdict_and_exits_on_it`), `src/devops_cli/lang/en/messages.py` (the class `PRMessages`). Changes: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`.

- [x] 1.1 Write the failing tests first. In `tests/github/test_merge_readiness.py` replace the table of the old warning with rows over `_assess`: a body with no `Closes` line gives one `BODY_FORM` blocker; a body with no `Closes` line and no `Change:` line gives two; a body of `None` gives both; a text over 1,000 characters gives a blocker that names the limit; a body in the form gives none; a plan pull request and a base without change folders give none. In `tests/commands/test_pr.py` replace the row `long-body` with a row for a body with no `Closes` line (exit 1, the problem in the output) and give the helper `_pr` a body in the form.
  - Verification: `uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py` fails on the base: no blocker of the kind `BODY_FORM` exists.
- [x] 1.2 In `src/devops_cli/lang/en/messages.py` replace `pr_body_too_long` with `body_form_problem`. In `src/devops_cli/github/merge_readiness.py` add `BlockerKind.BODY_FORM` and call `body_problems` in `_judge_grounding` for a pull request that is no plan. Delete `_judge_body_length`, `_PR_BODY_MAX_CHARS` and `_TRAILER_PREFIXES`.
  - Verification: `uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py` passes
- [x] 1.3 Check the callers that share the verdict
  - Verification: `uv run devops ci test tests/github tests/commands/test_pr.py tests/commands/test_pr_cmd.py tests/roadmap/test_roadmap_implement_job.py` passes

## 2. Name the blocker in CONTRIBUTING.md

Reads: `CONTRIBUTING.md` (section 4, the bullet "The Body Is the Commit Message"). Changes: `CONTRIBUTING.md`.

- [x] 2.1 In `CONTRIBUTING.md` section 4, replace the sentence about the warning with one that says `devops pr check-readiness` reports each problem of the form of the body and exits 1.
  - Verification: `git grep -n "the warning blocks nothing" -- CONTRIBUTING.md` prints nothing
- [x] 2.2 Check the documents
  - Verification: `uv run devops ci docs` and `uv run devops openspec check` pass

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
