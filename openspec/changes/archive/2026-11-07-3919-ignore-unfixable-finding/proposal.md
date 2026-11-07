# Proposal

## Why

A scanner can name a finding that no released version of the pinned package fixes. CVE-2026-78661 (HIGH) in golang.org/x/net, vendored in the pinned GitHub CLI binary, is the first case: no released `cli/cli` holds x/net 0.62.0, and the Runner Image and Service Image checks failed on every pull request. AGENTS.md rule 5 says only that the owner can allow a lower threshold, so an agent stops and asks. The owner decided on 2026-11-07 that an agent adds a time-limited ignore entry itself, and that each automatic entry expires after 3 days (#3919).

## What Changes

- `SECURITY.md` gets the section "A Finding with No Fix". It states when the rule applies and the proof the pull request comment must hold, the entry the agent adds (narrow scope, reason, tracking issue, `exp:` date 3 days ahead), the renewal (3 days each, 14 days in all, then the owner decides), what the agent never does, and the report.
- Rule 5 of `AGENTS.md` gets one clause that points to the section. Three short rewordings of other lines keep the file inside its character budget.
- `docs/ROUTINE_TASKS.md` gets a matrix row and a bullet in Cadence D that name the renewal of an ignore entry and point to `SECURITY.md`. They do not copy the rule.
- `CONTRIBUTING.md` and the task prompts under `src/devops_cli/ai/tasks` do not tell an agent to stop on a scanner finding, so they need no change.
- The entry for CVE-2026-78661 and its test belong to #3881 and are not part of this change.
- The change alters no behavior that a consumer observes: it edits documents. It has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `SECURITY.md`, `AGENTS.md`, `docs/ROUTINE_TASKS.md`

## Feasibility

- The Trivy documentation (filtering page, read on 2026-11-07) shows the `.trivyignore` line `CVE-2019-14697 exp:2023-01-01`, so an entry can expire by itself. The plain file has no path scope. The experimental `.trivyignore.yaml` holds `paths`, `purls`, `statement` and `expired_at`. The rule therefore says "as narrowly as the scanner allows".
- CI passes `.trivyignore` to the image scans (`.github/workflows/ci.yml`) and sets `ignore-unfixed: true`, so the ignore file is the only lever for a vendored library with no released fix.
- No task prompt under `src/devops_cli/ai/tasks` and no line of `CONTRIBUTING.md` tells an agent to stop on a scanner finding. A search for "scanner", "threshold" and "vulnerab" found none.
- `tests/invariants/test_agents_md_claims.py` already checks the character budget of `AGENTS.md` and that each relative link, with its heading anchor, resolves. The new pointer is therefore pinned by an existing test, and no new test is needed. The 3-day limit cannot be checked offline from the date in the entry.

## Existing Tool Considered

- Trivy `exp:` (and `expired_at` in the YAML format) already expires an ignore entry. The change adds no tool and no code.
- A new check that limits the date of an entry was rejected: the entry date is not in the file, so the limit cannot be checked offline. The reason, `exp:` date and tracking issue check belongs to #3881.
- The change deletes no code.
