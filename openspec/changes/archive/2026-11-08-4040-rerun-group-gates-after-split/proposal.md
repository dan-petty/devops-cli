# Proposal

## Why

When a group is over the token budget, `_Planner._fit` in `src/devops_cli/roadmap/stage/stage.py` asks the model to split the groups once. The split replaces `groups` and `criteria`. After it, `_Planner._settle` runs only five gates by hand: `form_problems`, `path_problems`, `search_problems`, `criterion_problems` and `creates_problems`. The other gates of `ProposalGate` read the groups too, and they do not run on the new groups. So a split can bring back a fault that only one of them refuses, and the job stages the plan (#4040).

## What Changes

- `_Planner._settle` in `src/devops_cli/roadmap/stage/stage.py` judges the split proposal with `check_proposal`, with the same arguments as the first pass. It removes the hand-made list of five gates.
- The gates `citation`, `dependencies` and `constants` read no group. They passed on the same input in the first pass, so they pass again at the cost of local reads.
- `tests/roadmap/stage/test_roadmap_stage_split_gates.py` scripts one split for each fault that only one gate refuses: `eval-replay`, `what-changes`, `move-prefix` and `registry`. Each case shows that `check_gates` finds problems under exactly one gate name, and that the planner sends that problem back to the model.
- The `roadmap-stage` capability gains one requirement: a split reply is judged by the gates of the first reply.
- The change stores nothing, adds no setting and removes, renames or tightens no key of `k8s/devops/configmap.example.yaml` or of the live ConfigMap, so it needs no load test of the example ConfigMap into `Settings`.
- The change does not type the request of the planner. That belongs to #4046.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A split reply is judged by every gate of the first reply

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_split_gates.py`

## Feasibility

- The premise holds at `origin/main` (release 0.85.0). `_Planner._settle` in `src/devops_cli/roadmap/stage/stage.py` calls `check_proposal` on the first reply. When `_fit` returns a proposal that is not the first one, `_settle` builds a list from `form_problems`, `path_problems`, `search_problems`, `criterion_problems` and `creates_problems` on `asked.groups`, and no other gate runs on them.
- `check_gates` in `src/devops_cli/roadmap/stage/stage_change.py` returns one key for each member of `ProposalGate`. `eval_replay_problems`, `_what_changes_problems`, `move_prefix_problems`, `move_verify_problems`, `registry_problems` and `content_problems` read `proposal.groups`, and `_delta_problems` reads the paths of the groups. `_plan_citation_problems`, `_overlap_problems` and `constant_problems` read the evidence fields, `dependencies` and `plan_texts`, which hold no group text. A split replaces only `groups` and `criteria`.
- The premise was checked with the test module of this change. On an unchanged `origin/main`, `uv run devops ci fail-to-pass --base origin/main` runs all eight cases and they fail: for each of the four faults, the planner accepts the split plan after two model calls where it must make three. `check_gates` on the same split proposal returns problems under exactly one gate name, so each case proves one gate.
- No merged change and no open pull request does this work. #4034 added `StageWriter` and does not touch `_settle`. `implement_run.py` has its own `ask_split` call, and the issue does not name it.

## Existing Tool Considered

`check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py` already covers the need. The change calls it again and builds no new check. It deletes the hand-made list of five gates in `_settle`. The written cost is about 25k tokens and 1.5 hours to build, about 2k tokens each quarter to keep, and about 8k tokens and 0.5 hours to fix.

## Dependencies

None.
