# Design

## Decisions

- **Put the rule in `finding_type_problems` and call it from `content_problems` in `src/devops_cli/roadmap/stage_change.py`.**: `check_proposal` and the replay both call `content_problems`, so one rule set judges both and the new rule needs no new seam.
- **Read only the free text of the plan: summary, why, group titles and task texts, spec delta texts, criteria texts and the pull request body.**: A finding type can appear in a task, a spec delta or the pull request body, and paths and structured values are not finding types.
- **Match a `DefectType.` reference anywhere, and a backticked `kind` or `type` with its value only in a sentence that names a finding or a defect.**: This catches the reported unknown kind and ignores the structured group kind `other`, which no verification sentence names.
- **Add `stage_problem_finding_type` to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`.**: No existing problem text lists the members of `DefectType`, and the planner needs those members in the one reply that the stage job already allows.
- **Return a problem that names the bad value and lists the members of `DefectType`.**: The planner can add the enum member or map the classification to `DefectType.OTHER`.
- **Write the plan's own free text so that the new rule accepts it.**: The rule refuses a sentence that names a finding or a defect and also holds a `kind` or `type` value outside `DefectType`. This plan therefore names the unknown value in a sentence with no such word, and a test on a synthetic proposal proves the trigger. Without this care the plan would refuse itself, and the same kind of plan would be refused on every later staging.
- **Test the helper through `content_problems`, not only through `check_proposal`.**: The replay calls `content_problems` directly, so a test on the shared check proves the rule in both paths.

## Rejected alternatives

- **Put the rule in `src/devops_cli/roadmap/stage_specs.py`.**: `src/devops_cli/roadmap/stage_specs.py` reads the base specs with `read_spec` and `read_base_specs` and judges no plan text.
- **Put the rule in the eval gates and rely on the golden set.**: `src/devops_cli/roadmap/stage_eval_cases.py` states that the golden set is a replay of recorded plans, so it proves a gate but never refuses a live plan.
- **Refuse every backticked token that is not a `DefectType` member.**: `tests/roadmap/test_roadmap_stage_plan.py` shows plans whose backticked tokens are paths and commands, such as `uv run devops ci docs`, so that rule refuses valid plans.
- **Scan every string field of the proposal.**: `src/devops_cli/roadmap/stage_change.py` validates `reads` and `changes` as repository paths and the group kind as `behavior` or `other`, so a scan of every string field reads values that are not finding types.
- **Scan the structured group kind as a finding type.**: Pydantic refuses a group kind outside `GroupKind` before `content_problems` sees the proposal, so that rule cannot catch the reported value.
- **Map an unknown value to `DefectType.OTHER` silently.**: `src/devops_cli/roadmap/stage_change.py` returns each rule break to the planner as a problem, and a silent mapping hides a design choice that the plan must state.
