# Proposal

## Why

The stage job accepts a `criteria` entry that no person wrote and writes it into `## Criteria` of `tasks.md` as one folded line. #3326 shows the result: a pasted `### Requirement: ... #### Scenario: ...` block, taken from the refine block, reaches the change. The implement job then verifies steps against a criterion that the issue does not hold, and the change hides that the issue gave none. The issue asks for clean requirement names instead; the exact copy of #3019 is the rule, so the check must refuse the entry that no person wrote and name it.

## What Changes

- Refuse each `criteria` entry whose text is not an acceptance criterion that a person wrote in the issue body, in `src/devops_cli/roadmap/stage/stage_criteria.py`.
- Add the message `stage_problem_criterion_unknown` to `src/devops_cli/lang/en/messages.py`; it quotes the entry and says that no person wrote it.
- Give the replay's `paths` gate the issue body of a plan that has a `criteria` list, in `src/devops_cli/roadmap/stage/stage_eval_gates.py`.
- State the refusal in the `criteria` bullet of `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Cover the refusal in `tests/roadmap/stage/test_roadmap_stage_criteria.py`, the body in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` and the prompt sentence in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- Keep the one-line fold and the character-for-character copy of the issue's criterion that #3019 and #3180 require, so the requirement titles of the spec delta stay out of `## Criteria`.
- The change alters what a `devops` message says and what the stage check refuses, so `skip_specs` is false and the delta adds two requirements to `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: An unmatched criteria entry is refused, The paths gate reads the body of a plan with a criteria list

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes moved the module that the issue cites. The probe says "The path `src/devops_cli/roadmap/stage_criteria.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_criteria.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." The plan cites `src/devops_cli/roadmap/stage/stage_criteria.py` and plans no code for the old path.
- The probe moved the plan-check module too. It says "The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`." The plan cites the moved path.
- The expected output of the issue, a requirement title in place of the issue's criterion, cannot be built as written. `src/devops_cli/roadmap/stage/stage_change.py:def criteria_section` folds each criterion with `_one_line`, and each line starts with a fixed word: `src/devops_cli/lang/en/messages.py:3670:stage_criteria_line: str = "Group {group}: {criterion}"`. #3019 and #3180 make the criterion the issue's list item copied character for character, which `src/devops_cli/roadmap/stage/stage_criteria.py:def acceptance_criteria` returns, so the plan keeps the copy and the fold and refuses the entry that no person wrote.
- The defect that the refine block names is in the code. `src/devops_cli/roadmap/stage/stage_criteria.py:def criterion_problems` builds `mapped` from the entry texts and refuses only a missing criterion and a group over the count, so no line compares an entry with the person-written list. `src/devops_cli/roadmap/stage/stage_change.py:def check_gates` routes that function under `ProposalGate.CRITERIA`, so one function keeps one source of truth for the match.
- The constants that the plan relies on are staged. `PENDING_PERSON: Final[str] = "pending-person"` is `src/devops_cli/roadmap/stage/stage_criteria.py:41:PENDING_PERSON: Final[str] = "pending-person"`. The refine block is cut off by `src/devops_cli/config/constants.py:3051:CONST_ROADMAP_REFINE_START_MARKER: Final[str] = "<!-- devops-roadmap-refine:start -->"` and `src/devops_cli/config/constants.py:3052:CONST_ROADMAP_REFINE_END_MARKER: Final[str] = "<!-- devops-roadmap-refine:end -->"`.
- The replay's paths gate holds no body today. `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _path_gate` calls `check_proposal` with no `issue_body`, while `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _criteria_gate` gives the criteria rule `plan.issue_body`. The existing assertion `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:311:assert not replay_case(_with_criteria(good, both)).refused` would refuse a plan whose entries copy its body once the refusal exists, so group 1 gives the paths gate the body first.
- The stage prompt holds the rule that the sentence joins. `search_code` of `An issue with no such list gets an empty list` returned the `criteria` bullet, and the file holds `src/devops_cli/ai/tasks/roadmap_stage_change.md:50:An issue with no such list gets an empty list.` beside `The check refuses a reply that leaves one item out.`
- The item repeats the defect of the open item #3391, whose change `openspec/changes/3391-refuse-criteria-entries-not-in-the/` plans the same refusal and modifies the base requirement `An unmapped criterion is refused`. Two active changes never modify one requirement (ADR 0010, `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`), so this change adds its rules under names of their own and leaves that requirement alone. The open item #4081 tracks the paths-gate coupling that group 1 repairs, and this change repairs it as part of the rule.
- No function that the change calls needs a client of a service or a network: `criterion_problems` and `acceptance_criteria` take strings, and `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _path_gate` takes a `PlanUnderTest` whose tree and body the replay reads from the recorded case files. `src/devops_cli/roadmap/plan_check.py:def _gate_problems` needs a checkout of the repository and a client of GitHub: it reads the staged tree with git and the issue body through `PlanReads`.
- The first checks against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, then `uv run devops roadmap eval stage --replay` with the score before and after the change.

## Existing Tool Considered

OpenSpec (Fission-AI/OpenSpec, MIT, last activity 2026-11-05, maintained) is the project's spec and change-proposal layer by `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`. It owns the spec delta with the requirement titles and the `#### Scenario:` blocks and validates them. It does not build `## Criteria`, map a criterion to a group, or refuse an entry that no person wrote, so the rule stays in `criterion_problems`. The change builds about 4k tokens of code to keep and fix, in about 1 hour, and deletes no internal code: `acceptance_criteria`, `criterion_problems` and `_path_gate` stay.

## Dependencies

None.
