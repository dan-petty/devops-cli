# Proposal

## Why

`devops pr check-readiness` holds every pull request into the default branch to the rules of a delivery: it closes one open item and it archives the change of that item. A plan pull request is not a delivery. It adds the active change folder, its body says `Plans #<issue>`, and it closes nothing (#3280). The command so reports two blockers on every valid plan, and a person must know to ignore them.

## What Changes

- `src/devops_cli/roadmap/grounding.py` gains `plan_issue(title)`, which reads the issue number of a title of the form `docs(openspec): plan #<issue> <summary>`, and `plan_blockers`, which holds the four rules of a plan: one `Plans #<issue>` line, no closing keyword, an added file under the active folder of the issue, and no path under `openspec/specs/`.
- `_judge_grounding` in `src/devops_cli/github/merge_readiness.py` applies those rules in place of the delivery rules when the title names a plan. It sends no closing-issues request for a plan.
- `lang/en/messages.py` holds one message for each plan rule.
- The change carries a spec delta for `pr-grounding`, because the readiness verdict is observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-grounding`: A plan pull request is judged by the rules of a plan, A plan body names its issue with one Plans line, A plan body uses no closing keyword, A plan adds the active change folder of its issue, A plan changes no living spec

## Impact

- Code: `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/SDLC.md`
- Tests: `tests/github/test_merge_readiness.py`, `tests/roadmap/test_grounding.py`

## Feasibility

- Command output: `uv run devops pr check-readiness 3261` on the open plan pull request #3261 printed `PR #3261 is not grounded: it closes no issue.` (see the body of #3280 for the second blocker). The premise holds.
- `src/devops_cli/github/merge_readiness.py` shows `_judge_grounding` calling `read_closing_issues` for every pull request into the default branch, and `src/devops_cli/roadmap/grounding.py` shows `GROUNDING_RULES` with `archives_its_change` and `closes_one_issue`, so a plan breaks both.
- `src/devops_cli/lang/en/messages.py` holds `stage_title_lead: str = "plan #{number} "`, and `staging_title` builds `docs(openspec): plan #<number> <summary>`, so the title is the one form that the stage job writes.
- `src/devops_cli/roadmap/stage_change.py` shows `closing_keyword_in`, which the stage job already uses to refuse a closing keyword in a plan body, so the rule reuses it.
- First check: `uv run devops ci test tests/github/test_merge_readiness.py tests/roadmap/test_grounding.py`.

## Existing Tool Considered

`devops pr check-readiness` is the existing command, and the change repairs it. The planned `devops roadmap plan-check` (#3201) judges the content of a plan, and not the merge readiness of its pull request, so it does not replace these rules. The cost to build is about 20,000 tokens and 1 hour, and about 3,000 tokens per year to keep. The change deletes no internal code.
