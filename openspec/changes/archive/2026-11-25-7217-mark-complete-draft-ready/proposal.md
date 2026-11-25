# Proposal: #7217

## Why

Issue #7217: rule 6 of `AGENTS.md` says "mark it ready only after the checks pass". The rule gives a limit and no duty, so an agent can complete its work, see the checks pass, and leave the pull request as a draft. The rule also does not name agent work, so a pull request can become ready while a review, a repair or a check of the report of a builder still runs. The owner direction of 2026-11-25 is that agents always mark a draft ready when all agent work on it is complete and its checks are complete.

## What Changes

- Rule 6 of `AGENTS.md`: "Always mark it ready when checks pass and no agent work remains."
- Rule 6 of `src/devops_cli/templates/AGENTS.md.j2`, which `devops ai agents` renders: the same duty with the command `devops pr ready <pr_number>`. The snapshot of the implement step that holds the rendered template changes with it.
- `CONTRIBUTING.md`, "Drafts First": the duty, what agent work is, and which agent marks the pull request ready.
- Step 6 of the `devops-pr-ci` skill in its three roots, and the apply guidance of `openspec/config.yaml`: the same condition.
- One test in `tests/invariants/test_agents_md.py`.
- The text that `devops ai agents` writes is observable, so the change carries a delta for `agent-instructions`. It fits in one pull request.

## Capabilities

### Modified Capabilities
- `agent-instructions`: rule 6 gives the duty to mark a draft ready when the checks pass and no agent work remains.

## Impact

- An agent session marks its own complete draft ready and does not leave it for a person.
- A draft stays a draft while a review, a repair or a check of the report of a builder remains, so a person does not merge a pull request that still changes.
- No command changes. `devops pr ready` refuses a pull request while a check runs or fails, as before.

## Feasibility

Confirmed in the worktree of the change:
- `AGENTS.md` had 4,478 characters against the cap of 4,500 (`CONST_AGENTS_MD_MAX_CHARS`, `test_agents_md_stays_within_character_budget` in `tests/invariants/test_agents_md.py`). With the new sentence it has 4,497.
- `test_the_template_holds_each_rule_of_agents_md_that_is_not_only_for_devops_cli` compares the rule titles of `AGENTS.md` and the template. The title of rule 6 does not change.
- `tests/invariants/test_skills.py` needs the same text of `devops-pr-ci/SKILL.md` in `.agents/skills`, `.claude/skills` and `.kilocode/skills`.
- `openspec/specs/pr-merge-readiness/spec.md` ("pr ready asks the readiness function"): `devops pr ready` exits 8 while a check runs and 1 when a check fails. The instruction cannot make a pull request with a failed check ready.

## Existing Tool Considered

`devops pr ready` and its draft readiness function cover the state of the checks. No tool can know that no agent work remains in a session, so that part is an instruction. No code is built.
