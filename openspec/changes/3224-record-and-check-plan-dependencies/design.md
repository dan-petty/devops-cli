# Design

## Decisions

- **Keep `dependencies` as a list of lines and give an issue entry the form `#<number>: <reason>`.**: The field and its gate come from #3252, and the stage job must still name each open overlap by number and shared path. A second field would carry one meaning in two places.
- **Read the issue number in `issue_dependencies`, beside `_overlap_problems` in `src/devops_cli/roadmap/stage/stage_change.py`.**: One module then holds the form of every entry of the same list, and the two readers cannot disagree about it.
- **Read each dependency issue through the `PlanReads` client that `plan_check` already takes.**: One read path answers one fact. The command passes the GitHub-backed client, the tests pass a fake, and the check reaches no network.
- **Report the problem under the path of `proposal.md` in the change folder with the rule `issue-dependency`.**: The dependency lives in the `## Dependencies` section of that file, so a person goes to the line that names the issue.
- **Keep the rule in `plan_check` and leave `plan_recheck` without an issue-state read.**: `src/devops_cli/roadmap/plan_recheck.py` reads every folder of the default branch and writes nothing to git or to GitHub, so a state read for each dependency of each folder would put a network call in a whole-tree pass.
- **Run `uv run devops roadmap eval stage --replay` in the group that changes the stage module, and state the score before and after the change.**: `src/devops_cli/roadmap/stage/stage_change.py` is a trigger path of the replay, and the replay is what proves that the new reader and the new prompt text refuse no plan that the gates accepted.

## Rejected alternatives

- **Add a new `issue_dependencies` field of integers to `StageProposal`.**: `StageProposal` already holds `dependencies` from #3252, and the reply schema, the prompt-rules test and `_overlap_problems` read it. Two fields would carry one meaning and a plan could name one issue in each.
- **Change `dependencies` to a list of integers.**: `_overlap_problems` in `src/devops_cli/roadmap/stage/stage_change.py` matches a pull request number and a shared path in the entry text, so an integer list would break the overlap gate of #3252.
- **Report an `issue-dependency` problem from `devops roadmap plan-recheck` as well.**: `src/devops_cli/roadmap/plan_recheck.py` reads every change folder on the default branch and calls no GitHub, so a state read for each dependency of each folder would add a network call to a whole-tree pass. The acceptance criteria of the issue name `plan-check`.
- **Call GitHub from inside the check.**: Every test would need a token and a network, and the check would fail offline. `PlanReads` already gives the check one injected read path, and `tests/roadmap/test_roadmap_plan_check.py` passes a fake.
- **Refuse the plan at stage time in `check_proposal`.**: The stage job reads no issue state, and an overlap entry names an open pull request by definition, so a stage-time rule would refuse every plan that holds an overlap.
