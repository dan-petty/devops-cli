# Proposal: Start the watch row in mode on

## Why

Closes #5056. Rule 5 of section 8 of ADR 0021 starts each new row in mode `plan`, and mode `plan` writes nothing to GitHub. The rule includes the row `watch`. But `watch` replaces the live rows `stage_ready` and `pr_conflicts` with no shim. If the build item #5024 obeys the rule, no plan draft becomes ready and no conflict comment is posted until a person changes the mode. If #5024 does not obey the rule, it breaks the record. The review of PR #5051 found this defect after the merge.

## What Changes

- ADR 0021, section 8, rule 5: only the new rows `resolve`, `group`, `split`, `fix-checks` and `fix-conflict` start in mode `plan`. The row `watch` starts in mode `on`.
- ADR 0021, the row `watch`: a new bullet "Fix due marks". `watch` sets the due mark of a fix row only when that row exists (#5027, #5028) and its mode is `plan` or `on`. Until the fix row is in mode `on`, a verdict of a bot pull request that goes to that row also gets the route of a pull request of a person. Thus a bot pull request with a conflict still gets the comment of `pr_conflicts`.
- ADR 0021, `## Status`: one paragraph for this amendment.
- No spec delta (`skip_specs: true`): the change adds documents only. #5024, #5027 and #5028 add their own deltas.

## Capabilities

None.

## Impact

- No behavior change. This pull request applies nothing to the cluster, the ConfigMap or a Secret. The Service code of #5024 waits for the "safe and vetted" call of the owner.
- The new status paragraph goes in the `## Status` section, which the alternatives check does not read (`_title_and_status` in `src/devops_cli/roadmap/adr.py` reads only the paragraphs straight after the title). Section 8 is not in `Considered Options`. So the ADR budget of #5049 does not change.

## Feasibility

- Rule 5 was read in ADR 0021 on `origin/main` b734eb331, line 147: "Each row starts in mode `plan`". Lines 75 and 192 say that `watch` replaces `stage_ready` and `pr_conflicts`.
- The live rows were read in `src/devops_cli/roadmap/run.py:706` (`_run_stage_ready_adapter`) and `:814` (`_run_pr_conflicts_adapter`). `src/devops_cli/roadmap/pr_conflicts.py:1-9` comments on each ready delivery pull request with a conflict, which includes a bot pull request that is not a draft.
- The plan of tracker #5014 gives the plan-mode start only to each new unit row ("Plan mode first for each new unit row").
- The body of #5024 deletes both old rows ("The rows stage_ready and pr_conflicts are gone from src/devops_cli/roadmap/run.py") and keeps only the fix due marks off ("mode off until the fix Job items"). #5027 and #5028 add the fix rows.

## Existing Tool Considered

The MADR form that the ADRs of `docs/adr/` use. No build.
