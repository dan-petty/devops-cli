## ADDED Requirements

### Requirement: The stage job and the command share the rules of a plan
The rules of the title, the body, the plan reader, the stage gates and the size of each group SHALL have one code path in `src/devops_cli/roadmap/plan_check.py`, which `devops roadmap plan-check` and the stage job both call on a change folder in memory with the checkout that the measure reads (`PlanFolder`). The command SHALL read the folder from the detached worktree of the head of the pull request.

#### Scenario: The plan of #5407 before its push
- **WHEN** `staged_problems` judges the change folder of the head of #5407 on a clone that tracks each file that the plan names
- **THEN** it gives one problem: `group-no-files` for group 2 in `tasks.md`, with the message that the CI job `Plan Check` printed for #5407 word for word

### Requirement: The check before the push leaves out the rules of the pull request
`staged_problems` SHALL NOT judge the check `Semantic PR title`, a base spec that moved after the plan commit, or an open issue that the plan depends on. An open dependency holds the merge until it closes, and it is no fault of the plan.

#### Scenario: A plan that names an open issue
- **WHEN** `staged_problems` judges a plan whose `## Dependencies` names an issue
- **THEN** it gives no problem and reads no issue
