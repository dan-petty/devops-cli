## Problem
PR #6009 (#5027) added `roadmap.model_jobs`: the most model Jobs (implement, stage and fix-checks) that run at once for all Service repositories together, with fix-checks Jobs first. Its code default is 2. Before #6009, each repository had its own one-Job lock, so the 7 repositories could run Jobs at the same time. With about 20 failing bot pull requests a day and fix Jobs first, 2 places can go mostly to fixes and starve new stage and implement work. The template does not set the value, so a deploy gives 2.

Owner, 2026-11-16: the cap is 6.

## Expected behavior
- `k8s/devops/configmap.example.yaml` sets `roadmap.model_jobs: 6` under `roadmap:`, with a comment that the owner chose 6 for all repositories together (implement, stage and fix-checks Jobs, fix Jobs first).
- The code default stays 2.
- After the merge, deploy-stack applies it together with the `roadmap.fix_checks.mode: "on"` of #6009, after the release that holds #6009.

## Related
- #5027, #6009, #5014.


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
