# Proposal

## Why

Issue #3259: `devops pr check-readiness` reads the body of the pull request but does not judge its form. The squash merge makes the body the commit message on `main`, and `body_problems` in `src/devops_cli/roadmap/pull_form.py` holds the rules of that form (#3198). `devops pr create` and the jobs already use it. A body that breaks the form still passes readiness, so a missing `Closes #<issue>` line is found only after the merge.

## What Changes

- `assess_merge_readiness` in `src/devops_cli/github/merge_readiness.py` calls `body_problems` on the body of a pull request and adds one blocker of the new kind `BlockerKind.BODY_FORM` for each problem it returns. `devops pr check-readiness` prints each blocker and exits 1. `devops pr monitor` names them. `devops pr ready` warns of them, as it does for every other blocker.
- The call is in the item rules of the verdict (`_judge_grounding`), so it applies where the base holds `openspec/changes/`, as the other form rules of the item do. A plan pull request is judged by its own rules (`plan_blockers`), so `body_problems` is not called for it.
- The old warning for a long body goes out. `body_problems` holds the same limit, so the warning and the new blocker would report one fault twice, and one blocker would contradict the rule that the warning blocks nothing. The function `_judge_body_length`, its two constants and the message `pr_body_too_long` are deleted.
- The text of a blocker is a new field of `PRMessages` in `src/devops_cli/lang/en/messages.py`. It names the pull request and holds the text of the problem.
- `CONTRIBUTING.md` section 4 says that `devops pr check-readiness` reports each problem of the form and exits 1, in place of the sentence about the warning.
- The spec `pr-merge-readiness` gets two ADDED requirements and two REMOVED requirements. A message and an exit code of a devops command are observable, so the change carries a spec delta.
- The change fits one pull request.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| `check-readiness` calls `body_problems` on the body | group 1 |
| It reports each problem that `body_problems` returns | group 1 (a body with no `Closes` line and no `Change:` line gives two blockers) |
| It exits non-zero on at least one problem | group 1 (a row of the table in `tests/commands/test_pr.py`) |
| A test with a body that has no `Closes #` line asserts the report and the exit | group 1 |

No criterion waits for a person. The issue says it waits on #2585: that issue is closed and its work is in the tree, so the wait is over.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: ADDED "A pull request body must keep the form" and "Every problem of the body is one blocker"; REMOVED "A long pull request body gets a warning" and "The body warning blocks nothing".

## Impact

- Code: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `CONTRIBUTING.md`, `openspec/specs/pr-merge-readiness/spec.md` (by archive).
- Tests: `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`, and the helpers of other tests that build a pull request without a body.

Code that the change reuses or keeps green:

- `body_problems` in `src/devops_cli/roadmap/pull_form.py`, unchanged.
- `_Verdict.block`, `Blocker` and `_render_merge_readiness`: a blocker already prints and exits 1, so the command needs no change.

## Feasibility

Checked on 2026-11-06 against `origin/main` at `235a807c`.

- `body_problems` exists. `git grep -n "def body_problems" -- src` prints `src/devops_cli/roadmap/pull_form.py:251`. It takes a string, reads no file and makes no request, and returns one text for each problem.
- `check-readiness` has the body. `assess_merge_readiness` takes the REST payload of the pull request, and `merge_readiness.py` already reads `pr_data.get("body")` in two places. GitHub reports `null` for an empty body, so the code reads `or ""`.
- The command does not call it yet. `git grep -n "body_problems" -- src` prints only `commands/pr.py` (`_form_checked`, for `pr create`), `pull_form.py` and its own use. No file under `src/devops_cli/github/` names it.
- The dependency is delivered. `uv run devops gh api repos/dan-petty/devops-cli/issues/2585 --jq .state` prints `closed`, and the archived change `2026-11-03-2585-check-readiness-warns-when-a-pull` is in the tree. The issue text that says the command is missing is out of date.
- The warning of #2585 repeats a rule of `body_problems`. Both limit the body to 1,000 characters (`BODY_MAX_CHARS` is `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`). The pull request of #3215 (`feat/3215-pull-form-in-jobs`) changes `pull_form.py`, `messages.py` and the job modules, and not `merge_readiness.py`, so the two do not collide in code.

## Existing Tool Considered

No open tool judges the form of a pull request body for this repository. The `Semantic PR title` action checks only the title. The change reuses `body_problems`, so it builds no parser. It adds about 15 lines, one message and a few test rows, and it deletes about 25 lines of the old warning: about 40,000 tokens to build, a few thousand a year to keep, and under one hour.
