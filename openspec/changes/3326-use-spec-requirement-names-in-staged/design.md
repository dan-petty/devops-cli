# Design

## Decisions

- **Add the refusal to `criterion_problems` in `src/devops_cli/roadmap/stage/stage_criteria.py`.**: That function is the one check that the stage job, the implement job and the plan check run on a `criteria` list, and `check_gates` already routes it under `ProposalGate.CRITERIA`, so one function keeps one source of truth for the match.
- **Add the rule under a requirement of its own and leave the base requirement `An unmapped criterion is refused` unmodified.**: The open change `openspec/changes/3391-refuse-criteria-entries-not-in-the/` modifies that requirement, and two active changes never modify one requirement, so each change archives without a conflict in `openspec/specs/roadmap-stage/spec.md`.
- **Give the replay's `paths` gate the issue body of a plan that has a `criteria` list, and no body for a plan that has none.**: `_path_gate` calls `check_proposal`, which runs the criteria rule; with no body every entry is unmatched, and the existing replay assertions would refuse a plan whose entries copy its issue.
- **Normalize an entry and a criterion with `_one_line` before the match.**: A copy that differs only in spacing stays valid, as the missing-criterion check already compares whole texts on one line.
- **Keep the one-line fold and the character-for-character copy of the issue's criterion.**: #3019 and #3180 make the criterion the issue's item as written, and #3262 makes each `## Criteria` line start with a fixed word so a criterion cannot start a heading or a task.

## Rejected alternatives

- **Name the criteria in `## Criteria` with the requirement titles of the spec delta.**: The issue's expected line conflicts with the exact copy that #3019 and #3180 require, and `criterion_problems` matches an entry to a criterion by that text (`src/devops_cli/roadmap/stage/stage_criteria.py:def criterion_problems`), so a requirement title would break the match that the check reads.
- **Render a criterion as markdown, with its heading and scenario lines.**: `src/devops_cli/roadmap/stage/stage_change.py:def criteria_section` folds each criterion with `_one_line` so that a criterion `## 2. X` is no heading of `tasks.md`, and the section is a plain bullet list with no box.
- **Leave the rule to the stage prompt and accept an entry that no person wrote.**: The prompt already states the empty-list rule, and `openspec/changes/3391-refuse-criteria-entries-not-in-the/design.md:16:The plan for #3320 in #3333 copied five refine-block criteria and every gate accepted it, although the prompt already stated the empty-list rule.`
- **Accept a substring of a criterion as a match.**: A partial text can match a different criterion and weaken the check; the missing-criterion rule compares whole texts, and the prompt requires the item copied character for character.
- **Let the replay's `paths` gate judge the criteria rule with no issue body.**: `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _path_gate` passes no `issue_body`, so the new rule would refuse the entries of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:311:assert not replay_case(_with_criteria(good, both)).refused`, which copies the criteria of its body.
