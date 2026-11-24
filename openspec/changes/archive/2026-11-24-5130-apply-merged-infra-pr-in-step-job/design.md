# Design

## Decisions

- **Decision: Run infra-apply as a roadmap step job**: The webhook router launches the `infra-apply` step job on pull request merge events.
- **Decision: Refuse repos below safe**: Only agent access levels `safe` and `full` permit applying changes to hosts. Repositories at `none` or `plan` refuse apply.
- **Decision: Plan merge commit before apply**: The job creates and verifies a plan for the merge commit before it applies that plan.
- **Decision: Stop before own node and control-plane node**: A cluster Job must not drain or reboot its own node or a control-plane node. The job stops before that host, cordons or uncordons no node, and tells the user to run on a workstation.
- **Decision: One comment per merge commit**: The job posts one marked comment on the merged pull request keyed by the merge commit SHA.
- **Decision: Keyed issue on failure**: The job creates or updates one issue keyed by the infra repo and host when an apply stops or fails.

## Rejected alternatives

- **Rejected: Workstation apply only**: Requires manual operator intervention for every merged pull request.
- **Rejected: Apply without plan verification**: Could apply unreviewed changes or failed plans.
- **Rejected: Drain own node**: Causes the runner pod to terminate abruptly during execution.
