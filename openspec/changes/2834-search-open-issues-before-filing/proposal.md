# Proposal

## Why

Issue #2834: AGENTS.md rule 11 tells an agent to file every failing or warning `devops` command with `devops roadmap intake`. It does not tell the agent to look for an open issue first. On 2026-10-30 two agents of one workflow saw the same failing check (`uv audit`) and filed #2808 and #2810. Intake flagged #2810 as a possible duplicate and filed it, as the owner rule of 2026-10-25 requires, and a person closed it.

## What Changes

- Rule 11 in `AGENTS.md` says to check the open issues first and to comment on a match. The rule keeps its filing command. The file has a cap of 6,500 characters (`tests/invariants/test_agents_md_claims.py`), so the rule repeats the sentence "Fix a defect at its source." as "at its source" in the title, and the search call lives in the document that owns the procedure.
- `docs/ROUTINE_TASKS.md`, item 6, names the exact search call (`devops gh api` on the search endpoint) and says to comment on the issue that covers the defect and file nothing.
- The change sets `skip_specs: true` in `.openspec.yaml`: it edits two documents. No command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `AGENTS.md`, `docs/ROUTINE_TASKS.md`.

## Feasibility

- Command output: `devops gh issues list --help` shows the options `--repo`, `--state`, `--milestone`, `--label` and `--limit`, and no search option. The search endpoint is the way to search.
- Command output: `devops gh api "search/issues?q=repo:dan-petty/devops-cli+is:issue+is:open+in:title,body+uv+audit&per_page=3" --jq .total_count` runs and returns a count.
- Command output: `wc -c AGENTS.md` gives 6,500 after the change, the cap of the budget test, so no text may be added to the file.
- Intake already flags a possible duplicate and never drops a candidate (owner rule of 2026-10-25). This change does not alter that rule. It moves the first check to the agent that files.

## Existing Tool Considered

The GitHub search API through `devops gh api`, which the project already uses. Nothing is built.
