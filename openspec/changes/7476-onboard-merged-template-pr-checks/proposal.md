# Proposal: #7476

## Why

Row 10 of `devops repos onboard` required a check name from the history of a repository (#7476). On 2026-11-27, `devops repos onboard dan-petty/devtools --confirm` found each template file on the default branch, so row 9 was `present`, and it read the check runs of the newest template pull request, dan-petty/devtools#99, which merged on 2026-11-26. The head of #99 reported `Semantic PR title` with `success` from the title workflow of that time. dan-petty/devtools#115 then took the template again, and the title check is now `PR title / Semantic PR title`. Row 10 added `Semantic PR title` to the ruleset `main`, no workflow reports that name, and each new pull request of devtools waits on it.

## What Changes

- Row 9 in `src/devops_cli/github/onboard/template_pr.py:def template_row` reads the check runs of the open template pull request only, also when the repository holds each template file. A merged or closed template pull request gives row 10 no check name and no check to drop, so row 10 keeps each live required check and adds the checks of the baseline and of `github/repository.yaml`.
- `_last_template_pull`, which listed the template pull requests in each state, goes: `_open_pull` gives the one pull request that row 10 reads.
- The first confirmed run keeps the rule of D3: row 9 opens the template pull request, waits for its checks, and row 10 requires the checks that ended `success`. The drop of a live check that only skipped (#7318) still works while the template pull request is open.
- `docs/repos/onboard.md` states the new rule of rows 9 and 10 and the person step for a required check of a repository whose template pull request merged.
- The change carries a spec delta for `repos-onboard`, because the states and the change lines of rows 9 and 10 are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-onboard`: Row 9 reads the checks of the open template pull request (renamed from Row 9 reads the checks of the newest template pull request), A skipped check run adds no required check

## Impact

- Code: `src/devops_cli/github/onboard/template_pr.py`
- Documents: `docs/repos/onboard.md`
- Tests: `tests/github/onboard/test_onboard_rows.py`
- A repository whose template pull request merged gets no `; dropped` line from history any more. A required check that no workflow reports there stays until a person removes it from the ruleset.

## Feasibility

- The issue body gives the run of 2026-11-27: row 9 `present` with dan-petty/devtools#99 merged, head `54ba00a`, and row 10 `applied` with `Semantic PR title` and `PR title / Semantic PR title` required.
- The source confirms the cause: `template_row` called `_last_template_pull` with `state=all` when the repository held each file, and set `ctx.successful_checks` from the head of that pull request; `_with_required_checks` in `src/devops_cli/github/onboard/settings_rows.py` adds each name of `_checks_to_require(successful, skipped)` to the desired ruleset.
- The new case `test_a_template_pull_request_that_is_not_open_gives_row_10_no_check` failed on the base commit in each of its three parameters: row 10 sent `PUT /repos/example-org/app/rulesets/7` with `Semantic PR title` added, or with `K8s` dropped. First check: `uv run devops ci test tests/github/onboard/test_onboard_rows.py`.
- Check against the real system: `uv run devops repos onboard dan-petty/devtools --plan --only 9,10` must not add `Semantic PR title` to row 10; it needs the token of the owner and a network.

## Existing Tool Considered

No open tool derives the required checks of a ruleset from the check runs of a template pull request; the change narrows code of #7318 and adds no logic. It deletes `_last_template_pull` from `src/devops_cli/github/onboard/template_pr.py`. Cost: about 1k tokens and 1 hour to build and keep.
