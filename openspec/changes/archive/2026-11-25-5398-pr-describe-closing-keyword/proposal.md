# Proposal: #5398

## Why

The proposal scaffold in `src/devops_cli/openspec/scaffold.py` asks authors to put `Closes #<issue>.` inside the `Why` section, yet `devops pr describe` refuses any closing keyword in `Why` even when it names the delivered issue itself (#5398).

## What Changes

- Remove `Closes #{issue}.` from the `Why` placeholder comment in `scaffold_proposal()` (`src/devops_cli/openspec/scaffold.py`), keeping `#{issue}` cited without a closing keyword.
- Reuse closing-keyword parsing in `src/devops_cli/roadmap/stage/stage_change.py` via a helper `strip_closing_keyword(text, issue)` that drops a closing clause targeting the delivered `issue` while leaving closing keywords targeting any other issue untouched.
- Update `proposal_why()` and `describe_pull()` in `src/devops_cli/roadmap/pull_describe.py` to strip a closing clause for the delivered `issue` before checking `closing_keyword_in()`, so `devops pr describe` drops self-closing text from legacy proposals and continues to refuse closing keywords for any other issue.
- Add tests in `tests/openspec/test_openspec_new.py` and `tests/commands/test_pr_describe.py` for the updated scaffold comment, stripped self-closing `Why` text, and refused cross-issue closing keywords.

## Capabilities

### Modified Capabilities
- `openspec-scaffold`: Remove the closing keyword from the `Why` placeholder comment in `scaffold_proposal`.
- `pull-request-form`: Drop a closing keyword naming the delivered issue in `devops pr describe` while continuing to refuse closing keywords for other issues.

## Impact

- `src/devops_cli/openspec/scaffold.py`
- `src/devops_cli/roadmap/stage/stage_change.py`
- `src/devops_cli/roadmap/pull_describe.py`
- `tests/openspec/test_openspec_new.py`
- `tests/commands/test_pr_describe.py`

## Feasibility

Confirmed on `origin/main` against source:
- `src/devops_cli/openspec/scaffold.py:72` writes `<!-- State the problem or motivation. Closes #{issue}. -->`.
- `src/devops_cli/roadmap/pull_describe.py:87-105` calls `closing_keyword_in(text)` without stripping the delivered issue's own closing clause.
- `tests/openspec/test_openspec_new.py:98` only requires `#3203` inside `Why`, so phrasing the comment without a closing keyword preserves existing contract tests.

## Existing Tool Considered

The alternatives check recorded `none` for this issue; no open tool reads this repository's `proposal.md` scaffold and `Closes` rules (`devops-cli` internal validation). Reusing `_CLOSING_KEYWORDS` and `_ISSUE_REFERENCE` in `stage_change.py` fixes both the scaffold and `pr describe` in ~15 lines (~15k tokens, <1 hour).
