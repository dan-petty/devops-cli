## Problem

The owner set a rule on 2026-11-16: "all jobs should have generous token limits because we don't yet know what is needed to get consistently successful results". The implement job's token budgets in `k8s/devops/configmap.example.yaml` are two times the code defaults (#5583): `step_token_budget` 16,000,000 and `item_token_budget` 40,000,000. Recent runs used much of the item budget before they stopped for other reasons: #3648 used 25.8M, #3529 23.4M, #3464 24.5M (`limit_reached` on 2026-11-15, while the live budgets were halved).

## Expected behavior

- `roadmap.implement.step_token_budget` is 32,000,000 and `item_token_budget` 80,000,000 in the template (four times the defaults); `step_token_ceiling` stays unset, so it is two times the step budget.
- The time limits do not change, so the item time (14400 s) still bounds a run.
- The template test and the spec requirement of the implement limits state the new factor for the two token budgets.
- New Service jobs (the fix Jobs of #5027, the review job of #5969) get generous token caps from the start.


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
