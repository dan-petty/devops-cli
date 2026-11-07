# Design

## Decisions

- **Put the count rule in the planner prompt and the proposal rule of `openspec/config.yaml`, and add no word rule to `check_proposal`.**: `every` and `no` are common in requirement text, so a word rule refuses valid plans; the prompt is the copy that the planner reads, and the planner cannot run a command.
- **Take the count from `references` or from a probe line, and say that the count is unverified when no tool can give it.**: The planner cannot run a command, so a command output written in the plan would be invented; the census command becomes the `verify` of the first group, and the implementation stops when its result differs from the plan.
- **Decide each member that the count finds as removed, restricted, or allowlisted with a reason.**: The guard of #3230 missed `k8s_diff_helm.values`, and a long exempt list hides a member that no one decided.
- **Count the set that the issue names, and not the set of its examples.**: The plan of #3236 counted the three examples and left the other 57 tools of the role tables with no decision.
- **Add two requirements to the existing `roadmap-stage` capability and create no capability.**: The purpose of `roadmap-stage` already covers the prompt rules of the stage job, and its spec holds the rules that the prompt and the config share.
- **Write the test first in one group that changes the prompt and the test module, and a second group that adds the config rule and the shared phrase.**: The stage job refuses a plan that changes the prompt unless a task runs the replay with the score before and after, and the phrase test fails until the file that holds each phrase holds it.

## Rejected alternatives

- **A word gate in `check_proposal` that refuses a plan whose text holds `every`, `all` or `no`.**: `every` and `no` are common in requirement text, and the base spec of `roadmap-stage` holds many requirements with those words, so the gate would refuse valid plans and need an exempt list.
- **A prompt rule that asks the plan to give the output of a census command.**: `src/devops_cli/ai/tasks/roadmap_stage_change.md` gives the planner no shell, so the output would be invented; the rule takes a count from a tool of the plan run or from a probe line instead.
- **A check in `devops roadmap stage` that runs the census itself.**: The plan check reads text and runs offline, while a census of published schemas needs a running program; the earlier estimate for that check was about 15k tokens and 1 hour.
- **Keep the claim as written and add an exempt list for the members that break it.**: The plan of #3236 named three of 60 tools, so its audit would fail on the first run, and an exempt list hides a member that no one decided.
