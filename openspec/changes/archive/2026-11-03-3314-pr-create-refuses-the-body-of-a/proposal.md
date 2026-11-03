# Proposal

## Why

`devops pr create` holds every body to the form of a delivery: a `Closes #<issue>` line. A plan pull request closes no issue, and its body has `Plans #<issue>`. The command so refuses a valid plan body, and no sanctioned command can open a plan pull request, because `devops gh api` sends no request body and AGENTS.md rule 7 forbids bare `gh` (#3314). #3280 (PR #3310) fixed `devops pr check-readiness` and left `pr create`.

## What Changes

- `src/devops_cli/roadmap/pull_form.py` gains `plan_body_problems(body, issue)`: the form of a plan body is one `Plans #<issue>` line, no closing keyword, a `Change:` line with the active folder of the same issue, and the bounds of a delivery body.
- `_form_checked` in `src/devops_cli/commands/pr.py` reads the title with `plan_issue` (`src/devops_cli/roadmap/grounding.py`, #3310) and judges a plan title with `plan_body_problems`. Any other title keeps `body_problems`.
- `lang/en/messages.py` holds the four new messages.
- The change carries a spec delta for `pull-request-form`, because the refusal of `pr create` is observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: The body ends with Closes and the Change line (for a delivery), A plan body has the Plans line and no closing keyword

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `CONTRIBUTING.md`
- Tests: `tests/commands/test_pr_form_check.py`

## Feasibility

- Command output on 2026-11-03: `uv run devops pr create -t "docs(openspec): plan #3236 revise scope to role tools" --body "Plans #3236 ..."` printed `The pull request breaks the form. Nothing was opened: The body has no line Closes #<issue>.` The premise holds.
- `src/devops_cli/commands/pr.py` shows `_form_checked` calling `body_problems(body)` for every title, and `src/devops_cli/roadmap/pull_form.py` shows `_closing_problems` requiring the `Closes` line.
- `src/devops_cli/roadmap/grounding.py` holds `plan_issue`, added by #3310, which reads the issue of a plan title.
- `uv run devops gh api --help` lists no option for a request body, so no other sanctioned command opens a pull request.
- First check: `uv run devops ci test tests/commands/test_pr_form_check.py`.

## Existing Tool Considered

`devops pr create` is the existing command, and the change repairs it. No open library judges the form of this project's pull request body. The cost to build is about 12,000 tokens and 45 minutes, and about 2,000 tokens per year to keep. The change deletes no internal code.
