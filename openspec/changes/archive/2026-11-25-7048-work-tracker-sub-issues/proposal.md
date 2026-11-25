# Proposal: #7048

## Why

Interactive agents call `devops roadmap return` on tracking issues (`type/epic` or issues with linked sub-issues or related deliverables) instead of inspecting and working their open sub-issues or related issues. Closes #7048.

## What Changes

- Update Rule 2 of `AGENTS.md`, Rule 2 of `src/devops_cli/templates/AGENTS.md.j2`, and the `devops-roadmap` skill copies (`.agents/skills/devops-roadmap/SKILL.md`, `.claude/skills/devops-roadmap/SKILL.md`, `.kilocode/skills/devops-roadmap/SKILL.md`) so agents never return a tracker and instead work its open sub-issues or related issues.
- Add a shared `tracker_work` helper in `src/devops_cli/roadmap/dependencies.py` that collects open sub-issues (with open blocker IDs via `open_blockers`) and open related `#<number>` links referenced in person-written body prose (`text_of_a_person`).
- Update `plan_return` in `src/devops_cli/roadmap/return_item.py` to reject any item with `item.is_tracker` via `DevOpsCLIError` listing its actionable open sub-issues and related open issues (or advising closing/splitting if none are open).
- Update `explain_item` and `render_explanation` in `src/devops_cli/roadmap/explain.py` (with messages in `src/devops_cli/lang/en/messages.py`) so `devops roadmap explain` on a tracker preserves refine/stage leave-out verdicts while printing open sub-issues, blocker status, and related open issues.
- Update `src/devops_cli/lang/en/help.py` (`HELP.roadmap.return_item`), `docs/ROADMAP_WORKFLOW.md`, and regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md`.

## Capabilities

### New Capabilities
- `roadmap-return`: Returning an unbuildable leaf roadmap item to `New` while refusing trackers (`item.is_tracker`) with actionable open sub-issue and related-issue guidance.

### Modified Capabilities
- `agent-instructions`: Require agents in `AGENTS.md`, `AGENTS.md.j2`, and `devops-roadmap/SKILL.md` never to return a tracker and instead work its open sub-issues or related issues, within `CONST_AGENTS_MD_MAX_CHARS`.
- `roadmap-explain`: Preserve tracker leave-out verdicts while listing open sub-issues (with blocker state) and open related issues on `devops roadmap explain <tracker>`.

## Impact

- Agents attempting `devops roadmap return` on a tracker receive an immediate error naming the sub-issues and related issues to work next rather than placing the tracker back in `status/new` where `refine` and `stage` skip it.
- Running `devops roadmap explain <tracker>` shows which open sub-issues are unblocked and what open related issues exist.

## Feasibility

Confirmed in `/workspaces/devops-cli/.data/agent/worktrees/w-7048`:
- `Item.is_tracker` (`src/devops_cli/roadmap/stores/store.py:638-642`) and `ItemTree.open_sub_issues` (`src/devops_cli/roadmap/stores/store.py:689-691`) already identify trackers and open sub-issues without extra GitHub requests per child.
- `open_blockers` (`src/devops_cli/roadmap/dependencies.py:30-62`) and `text_of_a_person` (`src/devops_cli/roadmap/body_hash.py:437-441`) already exist and avoid duplicating dependency and body-cleaning logic.
- `AGENTS.md` on `origin/main` (`4,471` characters) fits within `CONST_AGENTS_MD_MAX_CHARS` (`4,500`) after tightening redundant phrasing in Rule 2 and the role paragraph while keeping all assertions in `tests/invariants/test_agents_md.py`.

## Existing Tool Considered

No external library handles `devops-cli` tracker ownership and roadmap issue routing. Reusing `Item.is_tracker`, `ItemTree`, `open_blockers`, and `text_of_a_person` avoids rebuilding issue parsing; total implementation and test cost is ~20k tokens and ~1 hour.
