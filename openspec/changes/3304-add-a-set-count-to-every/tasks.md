# Tasks

## 1. Add the count rule to the stage prompt with its phrase test

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `openspec/changes/3236-read-only-tools-take-paths-that/design.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 1.1 Add `test_the_prompt_asks_for_a_count_of_a_claimed_set` to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. It asserts that the prompt holds `gives a count from a tool of the plan run or from a probe line`, `the count is unverified`, `census command`, `verify` of the first group, `removed, restricted, or allowlisted with a reason`, `a member with no decision`, `narrows the claim`, `follow-up issue`, `the set that the issue names` and `not the set of its examples`. Add `test_the_plan_check_refuses_no_word_of_a_requirement_text`, which builds a plan whose requirement text holds `every` with `make_stage_proposal` and asserts that `check_proposal` returns no problem that names the word. Both tests fail on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 1.2 Add one bullet to the rules of `src/devops_cli/ai/tasks/roadmap_stage_change.md`, after the feasibility bullet: a claim about every member of a set, or a new guard over a set, gives a count from `references` or from a probe line; when no tool can count the set, the plan says that the count is unverified, makes the census command the `verify` of the first group, and stops when the result differs from the plan; the plan decides each member as removed, restricted, or allowlisted with a reason, and a member with no decision fails the verification of the group that counts the set; a count above zero for a claim of no members narrows the claim or names the follow-up issue for the rest; the set is the set that the issue names, and not the set of its examples. Then run `uv run devops roadmap eval stage --replay` and state the score of the stage model before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 2. State the same rule in the proposal config and pin the shared phrase

Reads: `openspec/config.yaml`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/commands/test_openspec_scaffold.py`. Changes: `openspec/config.yaml`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 Add one item to `rules.proposal` of `openspec/config.yaml`, written as a folded scalar (`>-`): a claim about every member of a set, or a new guard over a set, gives a count from a tool of the plan run or from a probe line; when no tool can count the set, say that the count is unverified, make the census command the `verify` of the first group, and decide each member as removed, restricted, or allowlisted with a reason; a count above zero for a claim of no members narrows the claim or names the follow-up issue; the set is the set that the issue names, and not the set of its examples. Add the pair `("openspec/config.yaml", "gives a count from a tool of the plan run or from a probe line")` to `_SHARED` of `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
